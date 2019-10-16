import csv
import singer
from tap_sftp import client, conversion

LOGGER = singer.get_logger()

SDC_SOURCE_FILE_COLUMN = "_sdc_source_file"
SDC_SOURCE_LINENO_COLUMN = "_sdc_source_lineno"
SDC_EXTRA_COLUMN = "_sdc_extra"

def get_sampled_schema_for_table(conn, table_spec):
    LOGGER.info('Sampling records to determine table schema "%s".', table_spec['table_name'])

    files = conn.get_files(table_spec['search_prefix'], table_spec['search_pattern'])

    if not files:
        return {}

    samples = sample_files(conn, table_spec, files)

    metadata_schema = {
        SDC_SOURCE_FILE_COLUMN: {'type': 'string'},
        SDC_SOURCE_LINENO_COLUMN: {'type': 'integer'},
        SDC_EXTRA_COLUMN: {'type': 'array', 'items': {'type': 'string'}},
    }

    data_schema = conversion.generate_schema(samples)

    return {
        'type': 'object',
        'properties': merge_dicts(data_schema, metadata_schema)
    }

def sample_file(conn, table_spec, f, sample_rate, max_records):
    table_name = table_spec['table_name']
    plurality = "s" if sample_rate != 1 else ""
    LOGGER.info('Sampling %s (%s records, every %s record%s).', f['filepath'], max_records, sample_rate, plurality)

    samples = []

    file_handle = conn.get_file_handle(f)
    reader = csv.DictReader((line.replace('\0', '') for line in file_handle), restkey=SDC_EXTRA_COLUMN, delimiter=table_spec.get('delimiter', ','))

    # Check for the key_properties
    headers = set(reader.fieldnames)
    if table_spec.get('key_properties'):
        key_properties = set(table_spec['key_properties'])
        if not key_properties.issubset(headers):
            raise Exception('CSV file missing required headers: {}, file only contains headers for fields: {}'
                            .format(key_properties - headers, headers))

    # Check for date overrides
    if table_spec.get('date_overrides'):
        date_overrides = set(table_spec['date_overrides'])
        if not date_overrides.issubset(headers):
            raise Exception('CSV file missing date_overrides headers: {}, file only contains headers for fields: {}'
                            .format(date_overrides - headers, headers))

    current_row = 0
    for row in reader:
        if (current_row % sample_rate) == 0:
            if row.get(SDC_EXTRA_COLUMN):
                row.pop(SDC_EXTRA_COLUMN)
            samples.append(row)

        current_row += 1

        if len(samples) >= max_records:
            break

    LOGGER.info('Sampled %s records.', len(samples))

    # Empty sample to show field selection, if needed
    empty_file = False
    if len(samples) == 0:
        empty_file = True
        samples.append({name: None for name in iterator.fieldnames})

    return (empty_file, samples)

# pylint: disable=too-many-arguments
def sample_files(conn, table_spec, files,
                 sample_rate=1, max_records=1000, max_files=5):
    to_return = []
    empty_samples = []

    files_so_far = 0

    sorted_files = sorted(files, key=lambda f: f['last_modified'], reverse=True)

    for f in sorted_files:
        empty_file, samples = sample_file(conn, table_spec, f,
                                          sample_rate, max_records)

        if empty_file:
            empty_samples += samples
        else:
            to_return += samples

        files_so_far += 1

        if files_so_far >= max_files:
            break

    if not any(to_return):
        return empty_samples

    return to_return

def merge_dicts(first, second):
    to_return = first.copy()

    for key in second:
        if key in first:
            if isinstance(first[key], dict) and isinstance(second[key], dict):
                to_return[key] = merge_dicts(first[key], second[key])
            else:
                to_return[key] = second[key]

        else:
            to_return[key] = second[key]

    return to_return
