import sqlite3
import string


class InvalidLayoutError(Exception):
    def __init__(self, message, linenumber):
        self.message = f"\n\tError in layout file at line {linenumber}:\n\t{message}"
        super().__init__(self.message)


class BinaryParser():
    def __init__(self, layoutfname: str, byteorder='little', encoding='utf-8'):
        self.layoutfname = layoutfname
        self.byteorder = byteorder
        self.encoding = encoding
        self.sections = 0

    def __enter__(self):
        self.layout = open(self.layoutfname)
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
                baseoffset = int(baseoffset)
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

    def parseint(self, bytes):
        return int.from_bytes(bytes, self.byteorder)

    def parsestr(self, bytes: bytes):
        return ''.join([c for c in bytes.decode(self.encoding) if c.isalnum() or c.isspace() or c in string.punctuation])

    def paramstr(self, n):
        return f"({','.join(['?']*n)})"

    def create_query(self, tablename, columns):
        columnstring = ','.join(
            [f"`{column[0]}` {'TEXT' if column[1] == 'str' else 'INTEGER'}" for column in columns])
        query = f"CREATE TABLE IF NOT EXISTS `{tablename}` (id INTEGER PRIMARY KEY AUTOINCREMENT,{columnstring});"
        return query

    def insert_query(self, tablename, columnnames):
        columnstring = ', '.join(columnnames)
        querystring = f"INSERT INTO `{tablename}` ({columnstring}) VALUES {self.paramstr(len(columnnames))};"
        return querystring

    def parse_file(self, binaryfname, dst_path):
        f = open(binaryfname, 'rb')

        conn = sqlite3.connect(dst_path)
        for tablename, tableinfo in self.data.items():
            columns = []
            for section in tableinfo['sections']:
                for column in section['data']:
                    if column[0] != 'padding':
                        columns.append(column)

            query = self.create_query(tablename, columns)
            conn.execute(query)

            tablecolumnnames = []
            tabledata = [[] for _ in range(tableinfo['count'])]
            for section in tableinfo['sections']:
                sectioncolumnnames = [
                    name for name in
                    list(zip(*section['data']))[0] if name != 'padding']
                tablecolumnnames.extend(sectioncolumnnames)
                f.seek(section['offset'])
                for columndata in tabledata:
                    for name, type, _, length in section['data']:
                        if name == 'padding':
                            # Skip
                            f.read(length)
                            continue
                        if type == 'int':
                            columndata.append(self.parseint(f.read(length)))
                        elif type == 'str':
                            columndata.append(self.parsestr(f.read(length)))
            query = self.insert_query(tablename, tablecolumnnames)
            conn.executemany(query, tabledata)
        conn.commit()
        conn.close()
