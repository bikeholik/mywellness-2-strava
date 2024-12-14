import json
import os
import sys
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, ElementTree

def convert_json_to_tcx(json_file, output_tcx):
    """Convert a MyWellness JSON file to TCX format."""
    with open(json_file, 'r') as f:
        workout_data = json.load(f)

    # Determine start time
    json_date = workout_data['data']['date']
    total_duration = workout_data['data']['duration'] if 'duration' in workout_data['data'] else 0

    try:
        # Parse date and add computed time if needed
        parsed_date = datetime.strptime(json_date, "%d/%m/%Y")
        computed_time = datetime.utcnow() - timedelta(seconds=total_duration + 3600)
        start_time = parsed_date.replace(hour=computed_time.hour, minute=computed_time.minute, second=computed_time.second)
    except ValueError:
        # Fallback if parsing fails
        start_time = datetime.utcnow() - timedelta(seconds=total_duration + 3600)

    # Create the root XML structure
    training_center_database = Element('TrainingCenterDatabase', {
        'xmlns': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
        'xsi:schemaLocation': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 "
                              "http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
    })
    activities = SubElement(training_center_database, 'Activities')
    activity = SubElement(activities, 'Activity', {'Sport': 'Biking'})
    id_elem = SubElement(activity, 'Id')
    id_elem.text = start_time.isoformat() + "Z"  # ISO 8601 timestamp

    lap = SubElement(activity, 'Lap', {'StartTime': start_time.isoformat() + "Z"})
    total_time_elem = SubElement(lap, 'TotalTimeSeconds')
    total_time_elem.text = "0"  # Updated dynamically later
    lap_distance_elem = SubElement(lap, 'DistanceMeters')
    lap_distance_elem.text = "0"  # Updated dynamically later
    calories_elem = SubElement(lap, 'Calories')
    calories_elem.text = "0"  # Placeholder
    intensity_elem = SubElement(lap, 'Intensity')
    intensity_elem.text = "Active"

    # Tracks and metrics
    track = SubElement(lap, 'Track')
    descriptors = {desc['i']: desc['pr']['name'] for desc in workout_data['data']['analitics']['descriptor']}

    # Find indices for metrics
    power_index = next((k for k, v in descriptors.items() if v == 'Power'), None)
    distance_index = next((k for k, v in descriptors.items() if v == 'HDistance'), None)
    cadence_index = next((k for k, v in descriptors.items() if v == 'Rpm'), None)
    speed_index = next((k for k, v in descriptors.items() if v == 'Speed'), None)

    total_distance = 0.0
    total_time = 0.0

    # Extract heart rate data and map by timestamp
    heart_rate_data = {hr['t']: hr['hr'] for hr in workout_data['data']['analitics']['hr']} if 'hr' in workout_data['data']['analitics'] else {}

    # Add trackpoints
    for sample in workout_data['data']['analitics']['samples']:
        values = sample['vs']
        time_offset = sample['t']

        power = values[power_index] if power_index is not None else None
        distance = values[distance_index] if distance_index is not None else total_distance
        cadence = values[cadence_index] if cadence_index is not None else None
        speed = values[speed_index] if speed_index is not None else None
        heart_rate = heart_rate_data.get(time_offset)

        trackpoint_time = start_time + timedelta(seconds=time_offset)
        trackpoint = SubElement(track, 'Trackpoint')

        time_elem = SubElement(trackpoint, 'Time')
        time_elem.text = trackpoint_time.isoformat() + "Z"

        distance_elem = SubElement(trackpoint, 'DistanceMeters')
        total_distance = distance  # Use HDistance directly
        distance_elem.text = f"{total_distance:.2f}"

        if heart_rate is not None:
            hr_elem = SubElement(trackpoint, 'HeartRateBpm')
            hr_value = SubElement(hr_elem, 'Value')
            hr_value.text = str(int(heart_rate))

        if cadence is not None:
            cadence_elem = SubElement(trackpoint, 'Cadence')
            cadence_elem.text = str(int(cadence))

        if power is not None or speed is not None:
            ext_elem = SubElement(trackpoint, 'Extensions')
            tp_ext = SubElement(ext_elem, 'TPX', {'xmlns': 'http://www.garmin.com/xmlschemas/ActivityExtension/v2'})
            if speed is not None:
                speed_elem = SubElement(tp_ext, 'Speed')
                speed_elem.text = f"{speed / 3.6:.2f}"  # Convert km/h to m/s
            if power is not None:
                power_elem = SubElement(tp_ext, 'Watts')
                power_elem.text = str(int(power))

        total_time = time_offset

    # Update lap totals
    total_time_elem.text = f"{total_time:.2f}"
    lap_distance_elem.text = f"{total_distance:.2f}"

    # Write TCX file
    tree = ElementTree(training_center_database)
    with open(output_tcx, 'wb') as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)

    print(f"Converted JSON to TCX: {output_tcx}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mywellness_to_tcx.py <input_json_file>")
        sys.exit(1)

    input_json = sys.argv[1]
    base_name = os.path.splitext(os.path.basename(input_json))[0]
    output_tcx = f"{base_name}.tcx"

    convert_json_to_tcx(input_json, output_tcx)
