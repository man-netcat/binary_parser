class InvalidLayoutError(Exception):
    def __init__(self, message, linenumber):
        self.message = f"\n\tError in layout file at line {linenumber}:\n\t{message}"
        super().__init__(self.message)


class BinaryParser():
    def __init__(self, layoutfname):
        self.layoutfname = layoutfname
        self.sections = 0

    def __enter__(self):
        """Parses the layout file and adds offsets and data lenghts to a dictionary containing the data.
        """
        self.layout = open(self.layoutfname)
        self.parse_layout()
        return self

    def __exit__(self, type, value, traceback):
        # Exception handling here
        self.layout.close()

    def parse_layout(self):
        self.schema = {}
        line = ''
        lineno = 0
        while line != 'endfile':
            if line.startswith('begin'):
                self.sections += 1
                line = self.layout.readline().strip()
                lineno += 1
                try:
                    tablename, baseoffset, total, repetitions \
                        = line.split(' ')
                    baseoffset = int(baseoffset)
                    total = int(total)
                    repetitions = int(repetitions)
                except:
                    raise InvalidLayoutError(
                        'table must have four arguments', lineno)
                if not tablename in self.schema:
                    self.schema[tablename] = {}
                    self.schema[tablename]['columns'] = {}
                    self.schema[tablename]['count'] = repetitions

                dataoffset = 0
                line = self.layout.readline().strip()
                section_lineno = lineno
                lineno += 1
                subtotal = 0
                while line != 'end':
                    if line.startswith('padding'):
                        try:
                            _, datalen = line.split(' ')
                            datalen = int(datalen)
                            subtotal += datalen
                        except:
                            raise InvalidLayoutError(
                                'padding must have one argument', lineno)
                    else:
                        try:
                            dataname, datatype, datalen \
                                = line.split(' ')
                            datalen = int(datalen)
                            self.schema[tablename]['columns'][dataname] = [
                                datatype,
                                baseoffset+dataoffset,
                                datalen
                            ]
                            subtotal += datalen
                        except:
                            raise InvalidLayoutError(
                                'column must have three arguments', lineno)
                    dataoffset += datalen
                    line = self.layout.readline().strip()
                    lineno += 1
                if subtotal != int(total):
                    raise InvalidLayoutError(
                        f'lengths of section {tablename} do not add up to {total}', section_lineno)
            line = self.layout.readline().strip()
            lineno += 1
