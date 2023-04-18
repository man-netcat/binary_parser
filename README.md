# Binary File Parser

Provides a parser for a user-defined binary layout for easily reading a binary file given data offsets and lengths. After parsing the data, it can be stored in an sqlite database.

## Layout file format

```
begin
<table_name> <offset> <total_length> <repetitions>
    <column_name> <data_type> <data_length>
end
```

Each block signifies a contiguous block of data. Padding can be denoted as `padding <padding length>`.

## Example layout section

```
begin
table_1 0 10 3
    column_1 int 2
    column_2 str 8
end

begin
table_2 ...
    ...
end

endfile
```

In this example we show two sections for `table_1` and `table_2`. Section `table_1` starts at offset 0, has a total length of 10 and repeats three times in the binary file. It contains two items, `column_1` and `column_2`.  `column_1` is an integer value consisting of 2 bytes, and `column_2` is a string value consisting of 8 bytes. The sum of the item lengths must be equal to the total length described in the section definition. 

## Commandline usage

`python3 binary_parser.py <layout file> <binary file> <database file>`

## Example usage in Python project

```
def main():
    with BinaryParser('layout.lyt') as bp:
        bp.parse_file(binary_path, db_path)
```

This example opens the layout file `layout.lyt` and parses a given binary file given by `binary_path`, storing the parsed data in the database file given by `db_path`.
