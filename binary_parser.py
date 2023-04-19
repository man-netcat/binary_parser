import argparse
import sqlite3
import string


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

                dataoffset = 0
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
                            baseoffset+dataoffset,
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
                            baseoffset+dataoffset,
                            datalen
                        ))
                        subtotal += datalen
                    dataoffset += datalen
                    line = self.layout.readline().strip()
                    lineno += 1
                if subtotal != int(total):
                    raise InvalidLayoutError(
                        f'lengths of section {tablename} do not add up to {total}', section_lineno)
                self.data[tablename]['sections'].append({
                    'offset': baseoffset,
                    'data': section
                })
            line = self.layout.readline().strip()
            lineno += 1

    def bytes_to_int(self, bytes):
        return int.from_bytes(bytes, self.byteorder)  # type: ignore

    def bytes_to_str(self, bytes: bytes):
        return ''.join([c for c in bytes.decode(self.encoding) if c.isalnum() or c.isspace() or c in string.punctuation])

    def str_to_bytes(self, str: str):
        return bytearray(str, encoding=self.encoding)

    def int_to_bytes(self, int: int):
        return bytearray(int)

    def paramstr(self, n):
        return f"({','.join(['?']*n)})"

    def create_query(self, tablename, columns):
        columnstring = ','.join(
            [f"`{column[0]}` {'TEXT' if column[1] == 'str' else 'INTEGER'}({column[3]})" for column in columns])
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
                    for name, type, _, length in section['data']:
                        if name == 'padding':
                            # Skip
                            f.read(length)
                            continue
                        if type == 'int':
                            columndata.append(
                                self.bytes_to_int(f.read(length)))
                        elif type == 'str':
                            columndata.append(
                                self.bytes_to_str(f.read(length)))

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
                data = [item for sublist in cur.fetchall() for item in sublist]
                dataindex = 0
                for name, type, offset, _ in section['data']:
                    print(offset)
                    if name == 'padding':
                        continue
                    f.seek(offset)
                    if type == 'str':
                        f.write(self.str_to_bytes(data[dataindex]))
                    elif type == 'int':
                        f.write(self.int_to_bytes(data[dataindex]))
                    dataindex += 1

        conn.close()
        f.close()


def main():
    parser = argparse.ArgumentParser(
        prog='python3 binary_parser.py',
        description='Parses a binary file given a binary data layout file, a binary file and a database file to store the data in')
    parser.add_argument('layoutfile')
    parser.add_argument('binaryfile')
    parser.add_argument('database')
    args = parser.parse_args()

    with BinaryParser(args.layoutfile) as bp:
        bp.parse_file(args.binaryfile, args.database)


if __name__ == '__main__':
    main()
