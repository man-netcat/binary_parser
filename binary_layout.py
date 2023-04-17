class InvalidLayoutError(Exception):
    def __init__(self, message, linenumber):
        self.message = f"\n\tError in layout file at line {linenumber}:\n\t{message}"
        super().__init__(self.message)


class BinaryLayout():
    def __init__(self, layoutfname):
        self.layoutfname = layoutfname
        self.sections = 0

    def __enter__(self):
        self.layout = open(self.layoutfname)
        line = ''
        lineno = 0
        while line != 'endfile':
            if line.startswith('begin'):
                self.sections += 1
                line = self.layout.readline().strip()
                lineno += 1
                try:
                    name, _, total, _ = line.split(' ')
                except:
                    raise InvalidLayoutError(
                        'table must have four arguments', lineno)

                line = self.layout.readline().strip()
                section_lineno = lineno
                lineno += 1
                subtotal = 0
                while line != 'end':
                    if line.startswith('padding'):
                        try:
                            _, length = line.split(' ')
                            subtotal += int(length)
                        except:
                            raise InvalidLayoutError(
                                'padding must have one argument', lineno)
                    else:
                        try:
                            _, _, length = line.split(' ')
                            subtotal += int(length)
                        except:
                            raise InvalidLayoutError(
                                'column must have three arguments', lineno)
                    line = self.layout.readline().strip()
                    lineno += 1
                if subtotal != int(total):
                    raise InvalidLayoutError(
                        f'lengths of section {name} do not add up to {total}', section_lineno)
            line = self.layout.readline().strip()
            lineno += 1
        self.layout.seek(0)
        return self

    def __exit__(self, type, value, traceback):
        # Exception handling here
        self.layout.close()

    def read_layout(self) -> dict:
        self.schema = {}
        line = ''
        while line != 'endfile':
            if line.startswith('begin'):
                line = self.layout.readline().strip()
                tablename, baseoffset, total_length, repetitions \
                    = line.split(' ')
                baseoffset = int(baseoffset)
                total_length = int(total_length)
                repetitions = int(repetitions)

                if not tablename in self.schema:
                    self.schema[tablename] = {}
                    self.schema[tablename]['columns'] = {}
                    self.schema[tablename]['count'] = repetitions

                dataoffset = 0
                line = self.layout.readline().strip()
                while line != 'end':
                    if line.startswith('padding'):
                        _, datalen = line.split(' ')
                        datalen = int(datalen)
                    else:
                        dataname, datatype, datalen \
                            = line.split(' ')
                        datalen = int(datalen)
                        self.schema[tablename]['columns'][dataname] = \
                            [datatype,
                                baseoffset+dataoffset,
                                datalen]
                    dataoffset += datalen
                    line = self.layout.readline().strip()
            line = self.layout.readline().strip()
        return self.schema
