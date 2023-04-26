import argparse
import os
import sqlite3
import string
import sys

from layout_printer import LayoutPrinter
from PyQt5.QtWidgets import QApplication


class InvalidLayoutError(Exception):
    def __init__(self, message, linenumber):
        self.message = f"\n\tError in layout file at line {linenumber}:\n\t{message}"
        super().__init__(self.message)


class BinaryParser():
    def __init__(self, layout_path: str, byteorder='little', encoding='utf-8'):
        self.layout_path = layout_path
        self.byteorder = byteorder
        self.encoding = encoding
        self.sections = 0

    def __enter__(self):
        self.layout = open(self.layout_path)
        self.parse_layout()
        return self

    def __exit__(self, type, value, traceback):
        self.layout.close()

    def parse_layout(self):
        """Parses the layout file and adds offsets and data lenghts to a dictionary containing the data.
        """
        self.data = {}
        line = ''
        lineno = 0
        while line != 'endfile':
            if line.startswith('begin'):
                self.sections += 1
                line = self.layout.readline().strip()
                lineno += 1
                try:
                    tablename, baseoffset, total, counts = line.split(' ')
                except:
                    raise InvalidLayoutError(
                        'table must have four arguments', lineno)
                baseoffset = int(baseoffset, 0)  # Supports hexadecimal
                total = int(total)
                counts = int(counts)

                # Initialise table
                if not tablename in self.data:
                    self.data[tablename] = {
                        'sections': [],
                        'count': counts,
                    }

                if counts != self.data[tablename]['count']:
                    raise InvalidLayoutError(
                        f'Counts for table {tablename} must be equal for all sections of table {tablename}.', lineno)

                line = self.layout.readline().strip()
                section_lineno = lineno
                lineno += 1
                subtotal = 0
                section = []
                while line != 'end':
                    if line.startswith('padding'):
                        try:
                            _, datalen = line.split(' ')
                        except:
                            raise InvalidLayoutError(
                                'padding must have one argument', lineno)
                        datalen = int(datalen)
                        section.append((
                            'padding',
                            'int',
                            datalen
                        ))
                        subtotal += datalen
                    else:
                        try:
                            columnname, datatype, datalen \
                                = line.split(' ')
                        except:
                            raise InvalidLayoutError(
                                'column must have three arguments', lineno)
                        datalen = int(datalen)
                        section.append((
                            columnname,
                            datatype,
                            datalen
                        ))
                        subtotal += datalen
                    line = self.layout.readline().strip()
                    lineno += 1
                if subtotal != int(total):
                    raise InvalidLayoutError(
                        f'lengths of section {tablename} do not add up to {total}', section_lineno)
                self.data[tablename]['sections'].append({
                    'offset': baseoffset,
                    'data': section,
                    'length': total,
                    'counts': counts
                })
            line = self.layout.readline().strip()
            lineno += 1

    def paramstr(self, n):
        return f"({','.join(['?']*n)})"

    def create_query(self, tablename, columns):
        columnstring = ','.join(
            [f"`{column[0]}` {'TEXT' if column[1] == 'str' else 'INTEGER'}({column[2]})" for column in columns])
        query = f"CREATE TABLE IF NOT EXISTS `{tablename}` (id INTEGER PRIMARY KEY AUTOINCREMENT,{columnstring});"
        return query

    def insert_query(self, tablename, columnnames):
        columnstring = ', '.join(columnnames)
        querystring = f"INSERT INTO `{tablename}` ({columnstring}) VALUES {self.paramstr(len(columnnames))};"
        return querystring

    def parse_file(self, binary_path, db_path):
        f = open(binary_path, 'rb')

        conn = sqlite3.connect(db_path)

        for tablename, tablelayout in self.data.items():
            columns = [
                column
                for section in tablelayout['sections']
                for column in section['data']
                if column[0] != 'padding'
            ]

            query = self.create_query(tablename, columns)
            conn.execute(query)

            tablecolumnnames = list(zip(*columns))[0]

            tabledata = [[] for _ in range(tablelayout['count'])]

            for section in tablelayout['sections']:
                f.seek(section['offset'])

                for columndata in tabledata:
                    for name, type, length in section['data']:
                        if name == 'padding':
                            # Skip
                            f.read(length)
                            continue
                        bytes = f.read(length)
                        if type == 'int':
                            data = int.from_bytes(bytes, self.byteorder)
                        elif type == 'str':
                            data = bytes.decode(self.encoding)
                        else:
                            raise TypeError
                        columndata.append(data)

            query = self.insert_query(tablename, tablecolumnnames)
            conn.executemany(query, tabledata)

        conn.commit()
        conn.close()
        f.close()

    def select_query(self, tablename, section):
        columnnames = [column for column in list(
            zip(*section['data']))[0] if column != 'padding']
        query = f"SELECT {','.join([f'`{column}`' for column in columnnames])} FROM `{tablename}`"
        return query

    def write_back(self, binary_path, db_path):
        f = open(binary_path, 'rb+')

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        for tablename, tablelayout in self.data.items():
            for section in tablelayout['sections']:
                query = self.select_query(tablename, section)
                cur.execute(query)
                data = cur.fetchall()
                bytearr = bytearray()
                for entry in data:
                    idx = 0  # Index in the data entry without padding
                    for name, type, length in section['data']:
                        if name == 'padding':
                            # Fill section with zeroes
                            bytearr.extend([0x00 for _ in range(length)])
                        else:
                            if type == 'str':
                                # Convert string of chars to bytes
                                byteobj = bytearray(
                                    entry[idx], encoding=self.encoding)
                                print(len(byteobj))
                            elif type == 'int':
                                # Convert n-byte integer to bytes
                                byteobj = entry[idx].to_bytes(
                                    length, self.byteorder)
                            else:
                                raise TypeError
                            # Add the section to the byte array
                            bytearr.extend(byteobj)
                            idx += 1
                # Find offset in binary file to write to
                f.seek(section['offset'])
                f.write(bytearr)

        conn.close()
        f.close()

    def display_layout(self, binary_path):
        sections = sorted(
            [
                section
                for sections in [
                    table['sections']
                    for table in self.data.values()
                ]
                for section in sections
            ],
            key=lambda x: x['offset']
        )

        def get_bytes(length):
            return f.read(length).hex().upper()

        f = open(binary_path, 'rb')
        filesize = os.path.getsize(binary_path)
        unused_start = 0
        values = []

        for section in sections:
            section_start = section['offset']  # == unused_end
            section_end = section['offset'] + \
                section['length'] * section['counts']  # == next unused_start
            unused_length = section_start - unused_start

            if unused_length > 0:
                bytes = get_bytes(unused_length)
                values.append(('padding', 'int', unused_length, bytes))
            unused_start = section_end

            for _ in range(section['counts']):
                for value in section['data']:
                    bytes = get_bytes(value[2])
                    values.append((*value, bytes))

        lengthsum = sum([value[2] for value in values])
        unused_length = filesize - unused_start
        lengthsum += unused_length

        return values


def main():
    parser = argparse.ArgumentParser(
        prog='python3 binary_parser.py',
        description='Parses a binary file given a binary data layout file, a binary file and a database file to store the data in')
    modegroup = parser.add_mutually_exclusive_group(required=True)
    modegroup.add_argument(
        '-r',
        action='store_true',
        help='Use -r for reading a file and storing the data into a database.')
    modegroup.add_argument(
        '-w',
        action='store_true',
        help='Use -w to write the data from a database back into a binary file.')
    modegroup.add_argument(
        '-d',
        action='store_true',
        help='Use -d to display the binary file with the highlighted layout.')
    parser.add_argument(
        'layoutfile',
        help='The binary file describing the data layout of the binary file.')
    parser.add_argument(
        'binaryfile',
        help='The binary file to parse.')
    parser.add_argument(
        '-db',
        help='The database file for storing the data parsed from the binary file.', required=False)
    args = parser.parse_args()

    with BinaryParser(args.layoutfile) as bp:
        if args.r:
            if not args.database:
                print(
                    "Must provide a database for -r.\nPlease consult the instructions using -h.")
                exit()
            bp.parse_file(args.binaryfile, args.database)
        elif args.w:
            if not args.database:
                print(
                    "Must provide a database for -w.\nPlease consult the instructions using -h.")
                exit()
            bp.write_back(args.binaryfile, args.database)
        elif args.d:
            values = bp.display_layout(args.binaryfile)
            app = QApplication(sys.argv)
            window = LayoutPrinter()

            for value in values:
                if value[0] == 'padding':
                    window.write_text(value[3], color=False)
                else:
                    window.write_text(value[3], color=True)
            sys.exit(app.exec_())
        else:
            print(
                "No mode of operation provided.\nPlease consult the instructions using -h.")


if __name__ == '__main__':
    main()
