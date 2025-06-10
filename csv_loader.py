import csv
import os


def load_csv_data():
    """Load data from CSV files and return as dictionaries"""
    data_dir = 'data'

    # Load countries
    countries = {}
    country_file = os.path.join(data_dir, 'country.csv')
    if os.path.exists(country_file):
        try:
            with open(country_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        countries[int(row['id'])] = {
                            'name': row['name'],
                            'total_hotels': int(row.get('total_hotels', 0)),
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f'Error reading country file: {e}')

    # Load cities
    cities = {}
    city_file = os.path.join(data_dir, 'city.csv')
    if os.path.exists(city_file):
        try:
            with open(city_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        cities[int(row['id'])] = {
                            'name': row['name'],
                            'country_id': int(row['country_id']),
                            'total_hotels': int(row.get('total_hotels', 0)),
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f'Error reading city file: {e}')

    # Load areas
    areas = {}
    area_file = os.path.join(data_dir, 'area.csv')
    if os.path.exists(area_file):
        try:
            with open(area_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        areas[int(row['id'])] = {
                            'name': row['name'],
                            'city_id': int(row['city_id']),
                            'total_hotels': int(row.get('total_hotels', 0)),
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f'Error reading area file: {e}')

    # Load hotels - Handle NULL/empty area_id properly
    hotels = {}
    hotel_file = os.path.join(data_dir, 'hotel.csv')
    if os.path.exists(hotel_file):
        try:
            with open(hotel_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Handle empty area_id values properly
                        area_id = None
                        if row.get('area_id') and row['area_id'].strip():
                            try:
                                area_id = int(row['area_id'])
                            except ValueError:
                                area_id = None
                        
                        hotels[int(row['id'])] = {
                            'name': row['name'],
                            'city_id': int(row['city_id']),
                            'area_id': area_id,  # Can be None
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f'Error reading hotel file: {e}')

    # Load destinations
    destinations = []
    destination_file = os.path.join(data_dir, 'destination.csv')
    if os.path.exists(destination_file):
        try:
            with open(destination_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Handle empty string values that should be None
                        country_id = (
                            int(row['country_id'])
                            if row['country_id'] and row['country_id'].strip()
                            else None
                        )
                        city_id = (
                            int(row['city_id'])
                            if row['city_id'] and row['city_id'].strip()
                            else None
                        )
                        area_id = (
                            int(row['area_id'])
                            if row['area_id'] and row['area_id'].strip()
                            else None
                        )

                        destinations.append(
                            {
                                'id': int(row['id']),
                                'country_id': country_id,
                                'country_name': row.get('country_name', '').strip(),
                                'city_id': city_id,
                                'city_name': row.get('city_name', '').strip(),
                                'area_id': area_id,
                                'area_name': row.get('area_name', '').strip(),
                                'is_publish': int(row.get('is_publish', 1)),
                            }
                        )
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f'Error reading destination file: {e}')

    # If no countries were loaded from CSV but we have destinations with country names,
    # create countries from destination data
    if not countries and destinations:
        country_names = set()
        for dest in destinations:
            if dest['country_name'] and dest['country_id']:
                country_names.add((dest['country_id'], dest['country_name']))

        for country_id, country_name in country_names:
            countries[country_id] = {'name': country_name, 'total_hotels': 0}

    # Load hotel scores
    hotel_scores = {}
    hotel_scores_file = os.path.join(data_dir, 'top_100_hotel.csv')
    if os.path.exists(hotel_scores_file):
        try:
            with open(hotel_scores_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        hotel_scores[int(row['hotel_id'])] = {
                            'agoda_score': float(row['agoda_score']),
                            'google_score': float(row['google_score']),
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f'Error reading hotel scores file: {e}')

    # Load country outbound scores
    country_outbound = {}
    outbound_file = os.path.join(data_dir, 'country_outbound.csv')
    if os.path.exists(outbound_file):
        try:
            with open(outbound_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        country_outbound[int(row['country_id'])] = {
                            'expenditure_score': float(row['expenditure_score']),
                            'departure_score': float(row['departure_score']),
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f'Error reading country outbound file: {e}')

    return countries, cities, areas, hotels, destinations, hotel_scores, country_outbound


def get_sample_data():
    """Return sample data if CSV files are not available"""
    countries_data = {
        1: {'name': 'France', 'total_hotels': 0},
        2: {'name': 'United Kingdom', 'total_hotels': 0},
        3: {'name': 'United States', 'total_hotels': 0},
        4: {'name': 'Japan', 'total_hotels': 0},
    }
    cities_data = {
        1: {'name': 'Paris', 'country_id': 1, 'total_hotels': 320},
        2: {'name': 'London', 'country_id': 2, 'total_hotels': 270},
        3: {'name': 'New York', 'country_id': 3, 'total_hotels': 420},
        4: {'name': 'Tokyo', 'country_id': 4, 'total_hotels': 380},
    }
    areas_data = {
        1: {'name': 'Eiffel Tower', 'city_id': 1, 'total_hotels': 35},
        2: {'name': 'Buckingham Palace', 'city_id': 2, 'total_hotels': 15},
        3: {'name': 'Central Park', 'city_id': 3, 'total_hotels': 50},
        4: {'name': 'Shibuya Crossing', 'city_id': 4, 'total_hotels': 25},
    }
    # Sample hotels data
    hotels_data = {
        1: {'name': 'Hotel Le Meurice', 'city_id': 1, 'area_id': 1},
        2: {'name': 'The Ritz London', 'city_id': 2, 'area_id': 2},
        3: {'name': 'The Plaza', 'city_id': 3, 'area_id': 3},
        4: {'name': 'Park Hyatt Tokyo', 'city_id': 4, 'area_id': 4},
        5: {'name': 'Four Seasons Paris', 'city_id': 1, 'area_id': None},  # Hotel without area
    }
    # Sample hotel scores data
    hotel_scores_data = {
        1: {'agoda_score': 95.0, 'google_score': 87.0},
        2: {'agoda_score': 92.0, 'google_score': 89.0},
        3: {'agoda_score': 88.0, 'google_score': 85.0},
        4: {'agoda_score': 90.0, 'google_score': 91.0},
        5: {'agoda_score': 93.0, 'google_score': 88.0},
    }
    # Sample country outbound data  
    country_outbound_data = {
        1: {'expenditure_score': 75.0, 'departure_score': 65.0},
        2: {'expenditure_score': 70.0, 'departure_score': 60.0},
        3: {'expenditure_score': 85.0, 'departure_score': 55.0},
        4: {'expenditure_score': 80.0, 'departure_score': 70.0},
    }
    
    return countries_data, cities_data, areas_data, hotels_data, [], hotel_scores_data, country_outbound_data