import csv
from datetime import datetime

#Input and Output file path
input_file = "C:/Users/ZHANGD/Downloads/2024-006-1.txt"
output_csv = "C:/Users/ZHANGD/Downloads/TSG_Output.csv"
# Fluorescence Parameters
SCALE_FACTOR = 1.0
CLEAN_WATER_OFFSET = 0.0


def parse_line(line):


    parts = line.strip().split(',')  #Break line into parts and make sure line contains TSG
    if "$TSG" not in parts:
        return None

    try:

        #Reformat Date and Time and File_Break(Date-Time)
        time_str = parts[0].replace("UTC", "")
        date_str = parts[1]
        dt = datetime.strptime(date_str + time_str, "%d%m%y%H%M%S")
        date = dt.strftime("%Y-%m-%d")
        time = dt.strftime("%H:%M:%S")
        file_break = dt.strftime("%Y%m%d-") + "000000"  # First record will set the value per day

        idx = parts.index("$TSG") # Extract index of TSG and then get relevant fields
        temp_intake = float(parts[idx + 1])
        temp_lab = float(parts[idx + 2])
        conductivity = float(parts[idx + 3])
        fluorescence_voltage = float(parts[idx + 4])
        flow_rate = float(parts[idx + 5])
        flow_rate_fl = float(parts[idx + 6])
        latitude = float(parts[idx + 7])
        longitude = float(parts[idx + 8].split('*')[0])  # remove checksum after *

        fluorescence = SCALE_FACTOR * (fluorescence_voltage - CLEAN_WATER_OFFSET)
        temp_diff = temp_lab - temp_intake
        pressure = 4.5

        return {
            "Date": date,
            "Time": time,
            "Temperature:Intake": temp_intake,
            "Temperature:Lab": temp_lab,
            "Conductivity": conductivity,
            "Fluorescence": fluorescence,
            "Flow Rate": flow_rate,
            "Flow Rate-FL": flow_rate_fl,
            "Latitude": latitude,
            "Longitude": longitude,
            "Pressure": pressure,
            "Temperature:Difference": temp_diff,
            "File_Break": file_break
        }
    except Exception as e:
        print(f"Skipping line due to error: {e}")
        return None

def process_tsg_file(input_file, output_csv):
    first_record_time_by_day = {}
    data_rows = []

    with open(input_file, 'r') as f:
        for line in f:
            record = parse_line(line)
            if record:
                day_key = record["Date"]
                if day_key not in first_record_time_by_day:  # the "in" operator checks keys not values
                    first_record_time_by_day[day_key] = record["Time"]
                # Set consistent File_Break for the day
                record["File_Break"] = day_key.replace("-", "") + "-" + first_record_time_by_day[day_key].replace(":", "")
                data_rows.append(record)


    headers = list(data_rows[0].keys()) if data_rows else []
    units = [
        "n/a", "n/a", "deg C (ITS90)", "deg C (ITS90)", "S/m",
        "ug/L", "L/min", "L/min", "degrees", "degrees",
        "decibar", "degrees", "n/a"]

    with open(output_csv, 'w', newline='') as out_f:
        writer = csv.DictWriter(out_f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(dict(zip(headers, units)))
        writer.writerows(data_rows)

    print(f"Output written to: {output_csv}")

process_tsg_file(input_file, output_csv)
