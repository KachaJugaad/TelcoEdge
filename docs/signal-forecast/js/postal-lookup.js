/**
 * postal-lookup.js — Canadian Postal Code to Lat/Lon Geocoder
 *
 * Maps the first 3 characters of a Canadian postal code (FSA — Forward
 * Sortation Area) to approximate lat/lon coordinates.
 *
 * This is a static lookup table — no API call needed. Each FSA covers
 * a geographic area, so coordinates are approximate (centroid of area).
 *
 * For a full postal code (6 chars), we use the FSA centroid. This gives
 * accuracy within ~5-15 km which is sufficient for signal forecasting
 * (nearest tower is what matters, and towers are spaced > 1 km apart).
 *
 * Source: Canada Post FSA boundaries (public knowledge)
 */

// ============================================================================
// FSA Centroid Lookup Table
// ============================================================================

/**
 * Major FSA centroids for Canadian provinces/territories.
 * Format: { "FSA": [lat, lon] }
 *
 * This covers the most populated FSAs. For unknown FSAs, we interpolate
 * from the province letter prefix.
 */
const FSA_COORDS = {
  // Ontario — K (Eastern), L (Central), M (Toronto), N (SW), P (Northern)
  "K1A": [45.4215, -75.6972],   // Ottawa downtown
  "K1B": [45.4390, -75.6170],   // Ottawa east
  "K1C": [45.4750, -75.5530],   // Orleans
  "K1E": [45.4580, -75.5000],   // Cumberland
  "K1G": [45.4100, -75.6380],   // Alta Vista
  "K1H": [45.3850, -75.6680],   // Ottawa south
  "K1J": [45.4320, -75.5900],   // Gloucester
  "K1K": [45.4520, -75.6350],   // Vanier
  "K1L": [45.4410, -75.6580],   // Overbrook
  "K1M": [45.4450, -75.6800],   // Rockcliffe
  "K1N": [45.4300, -75.6850],   // Sandy Hill
  "K1P": [45.4230, -75.6980],   // Downtown
  "K1R": [45.4100, -75.7100],   // Centretown
  "K1S": [45.3950, -75.6900],   // Old Ottawa South
  "K1T": [45.3550, -75.6400],   // Gloucester South
  "K1V": [45.3700, -75.6200],   // Hunt Club
  "K1W": [45.4650, -75.5180],   // Navan
  "K1X": [45.3400, -75.5600],   // Leitrim
  "K1Y": [45.4050, -75.7350],   // Hintonburg
  "K1Z": [45.4100, -75.7500],   // Westboro
  "K2A": [45.3750, -75.7600],   // Carlingwood
  "K2B": [45.3600, -75.7900],   // Bayshore
  "K2C": [45.3400, -75.7600],   // Merivale
  "K2E": [45.3200, -75.7200],   // Greenboro
  "K2G": [45.3300, -75.7600],   // Baseline
  "K2H": [45.3300, -75.8200],   // Bell Corners
  "K2J": [45.3000, -75.7400],   // Barrhaven
  "K2K": [45.3400, -75.9100],   // Kanata
  "K2L": [45.3200, -75.8800],   // Kanata South
  "K2M": [45.3050, -75.8700],   // Kanata Lakes
  "K2P": [45.4130, -75.6950],   // Centretown
  "K2R": [45.2600, -75.7700],   // Manotick
  "K2S": [45.3900, -75.9200],   // Stittsville
  "K2T": [45.3600, -75.9200],   // Kanata
  "K2V": [45.3500, -75.9500],   // Kanata West
  "K2W": [45.3400, -76.0000],   // Carp
  "K4A": [45.4800, -75.4700],   // Cumberland
  "K4B": [45.5000, -75.0600],   // Rockland
  "K4C": [45.4100, -75.0700],   // Embrun
  "K4K": [44.2300, -76.4800],   // Kingston
  "K4M": [45.2800, -75.5200],   // Kemptville
  "K4P": [45.2500, -75.6300],   // Manotick
  "K6A": [44.5900, -75.6800],   // Brockville
  "K6H": [44.3500, -76.5300],   // Kingston
  "K6J": [45.0100, -74.7300],   // Cornwall
  "K6K": [45.0200, -74.7500],   // Cornwall West
  "K6V": [44.3000, -78.3200],   // Peterborough
  "K7A": [44.2600, -76.5100],   // Kingston
  "K7K": [44.2300, -76.4900],   // Kingston
  "K7L": [44.2300, -76.5000],   // Kingston
  "K7M": [44.2500, -76.5500],   // Kingston West
  "K8A": [44.3800, -77.4000],   // Trenton
  "K8N": [44.1500, -77.3800],   // Belleville
  "K8P": [44.1700, -77.3800],   // Belleville
  "K8V": [44.3600, -78.7400],   // Lindsay
  "K9A": [44.3000, -78.3200],   // Peterborough
  "K9H": [44.3000, -78.3200],   // Peterborough
  "K9J": [44.3000, -78.3200],   // Peterborough
  "K9K": [44.3000, -78.3200],   // Peterborough
  "K9L": [44.3000, -78.3200],   // Peterborough
  "K9V": [44.1000, -78.7500],   // Lindsay

  // Toronto GTA
  "M1B": [43.8060, -79.1940],   // Scarborough
  "M1C": [43.7850, -79.1600],   // Rouge
  "M1E": [43.7650, -79.1870],   // Guildwood
  "M1G": [43.7700, -79.2160],   // Woburn
  "M1H": [43.7700, -79.2400],   // Cedarbrae
  "M1J": [43.7440, -79.2350],   // Scarborough Village
  "M1K": [43.7270, -79.2620],   // Kennedy Park
  "M1L": [43.7110, -79.2850],   // Golden Mile
  "M1M": [43.7160, -79.2390],   // Cliffcrest
  "M1N": [43.6920, -79.2650],   // Birch Cliff
  "M1P": [43.7570, -79.2730],   // Dorset Park
  "M1R": [43.7500, -79.2950],   // Wexford
  "M1S": [43.7940, -79.2620],   // Agincourt
  "M1T": [43.7840, -79.3040],   // Tam O'Shanter
  "M1V": [43.8150, -79.2830],   // Milliken
  "M1W": [43.8000, -79.3180],   // L'Amoreaux
  "M1X": [43.8360, -79.2060],   // Highland Creek
  "M2H": [43.8030, -79.3540],   // Hillcrest Village
  "M2J": [43.7780, -79.3470],   // Fairview
  "M2K": [43.7870, -79.3860],   // Bayview Village
  "M2L": [43.7570, -79.3740],   // Silver Hills
  "M2M": [43.7890, -79.4150],   // Willowdale
  "M2N": [43.7700, -79.4100],   // Willowdale
  "M2P": [43.7530, -79.4000],   // York Mills
  "M2R": [43.7820, -79.4480],   // Lansing
  "M3A": [43.7530, -79.3300],   // Don Mills
  "M3B": [43.7450, -79.3520],   // Don Mills
  "M3C": [43.7250, -79.3400],   // Don Mills
  "M3H": [43.7540, -79.4430],   // Bathurst Manor
  "M3J": [43.7680, -79.4870],   // York University
  "M3K": [43.7370, -79.4650],   // Downsview
  "M3L": [43.7390, -79.5090],   // Downsview
  "M3M": [43.7280, -79.4950],   // Downsview
  "M3N": [43.7600, -79.5200],   // Downsview
  "M4A": [43.7250, -79.3150],   // Victoria Village
  "M4B": [43.7070, -79.3100],   // Parkview Hill
  "M4C": [43.6950, -79.3180],   // Woodbine Heights
  "M4E": [43.6770, -79.2930],   // The Beaches
  "M4G": [43.7090, -79.3630],   // Leaside
  "M4H": [43.7050, -79.3490],   // Thorncliffe Park
  "M4J": [43.6860, -79.3390],   // East York
  "M4K": [43.6790, -79.3520],   // The Danforth
  "M4L": [43.6690, -79.3150],   // East Toronto
  "M4M": [43.6590, -79.3400],   // Leslieville
  "M4N": [43.7280, -79.3880],   // Lawrence Park
  "M4P": [43.7120, -79.3920],   // Davisville
  "M4R": [43.7150, -79.4050],   // North Toronto
  "M4S": [43.7040, -79.3880],   // Davisville
  "M4T": [43.6890, -79.3830],   // Moore Park
  "M4V": [43.6860, -79.3980],   // Summerhill
  "M4W": [43.6790, -79.3880],   // Rosedale
  "M4X": [43.6680, -79.3720],   // Cabbagetown
  "M4Y": [43.6650, -79.3830],   // Church-Wellesley
  "M5A": [43.6540, -79.3600],   // Regent Park
  "M5B": [43.6560, -79.3790],   // Ryerson
  "M5C": [43.6510, -79.3710],   // St. Lawrence
  "M5E": [43.6470, -79.3730],   // Harbourfront
  "M5G": [43.6570, -79.3870],   // Central Toronto
  "M5H": [43.6520, -79.3830],   // Financial District
  "M5J": [43.6420, -79.3810],   // Harbourfront
  "M5K": [43.6480, -79.3850],   // Toronto Islands
  "M5L": [43.6490, -79.3810],   // Commerce Court
  "M5M": [43.7330, -79.4170],   // Bedford Park
  "M5N": [43.7110, -79.4190],   // Roselawn
  "M5P": [43.6970, -79.4120],   // Forest Hill
  "M5R": [43.6720, -79.4050],   // The Annex
  "M5S": [43.6620, -79.3960],   // University of Toronto
  "M5T": [43.6530, -79.4000],   // Chinatown
  "M5V": [43.6430, -79.3950],   // CityPlace
  "M5W": [43.6460, -79.3860],   // Stn Dominion
  "M5X": [43.6480, -79.3820],   // First Canadian Place
  "M6A": [43.7180, -79.4450],   // Lawrence Manor
  "M6B": [43.7090, -79.4510],   // Glencairn
  "M6C": [43.6940, -79.4280],   // Humewood
  "M6E": [43.6890, -79.4530],   // Caledonia
  "M6G": [43.6700, -79.4230],   // Christie
  "M6H": [43.6690, -79.4400],   // Dufferin Grove
  "M6J": [43.6470, -79.4200],   // Trinity-Bellwoods
  "M6K": [43.6360, -79.4280],   // Parkdale
  "M6L": [43.7130, -79.4900],   // Downsview
  "M6M": [43.6920, -79.4760],   // Silverthorn
  "M6N": [43.6730, -79.4700],   // The Junction
  "M6P": [43.6610, -79.4630],   // High Park
  "M6R": [43.6490, -79.4560],   // Parkdale
  "M6S": [43.6510, -79.4800],   // Runnymede
  "M8V": [43.6050, -79.5010],   // New Toronto
  "M8W": [43.6020, -79.5350],   // Long Branch
  "M8X": [43.6530, -79.5070],   // The Kingsway
  "M8Y": [43.6360, -79.4970],   // Mimico
  "M8Z": [43.6230, -79.5240],   // South Etobicoke
  "M9A": [43.6670, -79.5320],   // Islington City Centre
  "M9B": [43.6510, -79.5550],   // West Deane Park
  "M9C": [43.6430, -79.5780],   // Markland Wood
  "M9L": [43.7560, -79.5610],   // Humber Summit
  "M9M": [43.7240, -79.5360],   // Humberlea
  "M9N": [43.7060, -79.5180],   // Weston
  "M9P": [43.6960, -79.5320],   // Westmount
  "M9R": [43.6890, -79.5540],   // Kingsview Village
  "M9V": [43.7390, -79.5880],   // Silverstone
  "M9W": [43.7060, -79.5930],   // Rexdale

  // GTA surrounds — L prefix
  "L1A": [43.8700, -78.8470],   // Whitby
  "L1B": [43.8710, -78.7950],   // Whitby
  "L1C": [43.8650, -78.8200],   // Whitby
  "L1G": [43.8950, -78.8650],   // Oshawa
  "L1H": [43.8900, -78.8800],   // Oshawa
  "L1J": [43.8800, -78.8500],   // Oshawa
  "L1K": [43.9000, -78.9500],   // Courtice
  "L1L": [43.8550, -78.9500],   // Ajax
  "L1N": [43.8600, -78.8800],   // Oshawa
  "L1S": [43.8400, -79.0800],   // Ajax
  "L1T": [43.8600, -79.0700],   // Ajax
  "L1V": [43.8350, -79.1000],   // Pickering
  "L1W": [43.8400, -79.0500],   // Pickering
  "L1X": [43.8800, -79.0800],   // Pickering
  "L1Z": [43.8500, -79.0300],   // Ajax
  "L3P": [43.8500, -79.3000],   // Markham
  "L3R": [43.8500, -79.3500],   // Markham
  "L3S": [43.8800, -79.2500],   // Markham
  "L3T": [43.8200, -79.4000],   // Thornhill
  "L3Y": [44.0500, -79.4600],   // Newmarket
  "L3Z": [44.0200, -79.4300],   // Newmarket
  "L4A": [44.0600, -79.4700],   // Newmarket
  "L4B": [43.8500, -79.3800],   // Richmond Hill
  "L4C": [43.8700, -79.4400],   // Richmond Hill
  "L4E": [43.9400, -79.4600],   // Aurora
  "L4G": [43.9900, -79.4400],   // Aurora
  "L4H": [43.8000, -79.5800],   // Woodbridge
  "L4J": [43.8100, -79.4300],   // Concord
  "L4K": [43.8100, -79.5300],   // Concord
  "L4L": [43.8200, -79.5600],   // Woodbridge
  "L4S": [43.8600, -79.4300],   // Richmond Hill
  "L4T": [43.7200, -79.6200],   // Malton
  "L4V": [43.7000, -79.6300],   // Malton
  "L4W": [43.6600, -79.6100],   // Mississauga
  "L4X": [43.5900, -79.5700],   // Mississauga
  "L4Y": [43.6100, -79.5600],   // Mississauga
  "L4Z": [43.6200, -79.6200],   // Mississauga
  "L5A": [43.5800, -79.6300],   // Mississauga
  "L5B": [43.5900, -79.6500],   // Mississauga
  "L5C": [43.5700, -79.6100],   // Mississauga
  "L5E": [43.5600, -79.5800],   // Port Credit
  "L5G": [43.5500, -79.5900],   // Port Credit
  "L5H": [43.5500, -79.6100],   // Port Credit
  "L5J": [43.5200, -79.6500],   // Clarkson
  "L5K": [43.5300, -79.6400],   // Clarkson
  "L5L": [43.5500, -79.6500],   // Mississauga
  "L5M": [43.5600, -79.6800],   // Streetsville
  "L5N": [43.5800, -79.7200],   // Meadowvale
  "L5R": [43.6000, -79.6500],   // Mississauga
  "L5S": [43.6300, -79.6600],   // Malton
  "L5T": [43.6500, -79.6500],   // Mississauga
  "L5V": [43.5700, -79.7300],   // Meadowvale
  "L5W": [43.5900, -79.7100],   // Meadowvale
  "L6A": [43.8800, -79.4800],   // Maple
  "L6B": [43.8600, -79.3700],   // Markham
  "L6C": [43.8700, -79.3500],   // Markham
  "L6E": [43.8900, -79.2800],   // Markham
  "L6G": [43.8700, -79.2400],   // Markham
  "L6H": [43.4600, -79.7000],   // Oakville
  "L6J": [43.4500, -79.6800],   // Oakville
  "L6K": [43.4400, -79.6700],   // Oakville
  "L6L": [43.4300, -79.7100],   // Oakville
  "L6M": [43.4200, -79.7400],   // Oakville
  "L6P": [43.7900, -79.7000],   // Brampton
  "L6R": [43.7500, -79.7300],   // Brampton
  "L6S": [43.7700, -79.6800],   // Brampton
  "L6T": [43.7300, -79.7000],   // Brampton
  "L6V": [43.6900, -79.7600],   // Brampton
  "L6W": [43.7100, -79.7500],   // Brampton
  "L6X": [43.7200, -79.7700],   // Brampton
  "L6Y": [43.7000, -79.7300],   // Brampton
  "L6Z": [43.7400, -79.7700],   // Brampton
  "L7A": [43.7300, -79.8000],   // Brampton
  "L7B": [43.9100, -79.4900],   // King City
  "L7C": [43.7800, -79.7500],   // Brampton
  "L7E": [43.8500, -79.7000],   // Bolton
  "L7G": [43.7600, -79.9600],   // Georgetown
  "L7J": [43.7400, -79.5700],   // Woodbridge
  "L7K": [43.8600, -79.8500],   // Caledon
  "L7L": [43.3800, -79.8000],   // Burlington
  "L7M": [43.3700, -79.8200],   // Burlington
  "L7N": [43.3500, -79.7900],   // Burlington
  "L7P": [43.3600, -79.8400],   // Burlington
  "L7R": [43.3400, -79.8000],   // Burlington
  "L7S": [43.3300, -79.7900],   // Burlington
  "L7T": [43.3500, -79.8600],   // Burlington
  "L8E": [43.2200, -79.7500],   // Stoney Creek
  "L8G": [43.2300, -79.7800],   // Stoney Creek
  "L8H": [43.2400, -79.8200],   // Hamilton East
  "L8J": [43.2100, -79.7300],   // Stoney Creek
  "L8K": [43.2200, -79.7900],   // Stoney Creek
  "L8L": [43.2500, -79.8600],   // Hamilton
  "L8M": [43.2500, -79.8700],   // Hamilton
  "L8N": [43.2560, -79.8710],   // Hamilton
  "L8P": [43.2500, -79.8800],   // Hamilton
  "L8R": [43.2600, -79.8700],   // Hamilton
  "L8S": [43.2600, -79.8900],   // Westdale
  "L8T": [43.2400, -79.8500],   // Hamilton
  "L8V": [43.2300, -79.8600],   // Hamilton Mountain
  "L8W": [43.2100, -79.8700],   // Hamilton Mountain
  "L9A": [43.2400, -79.9000],   // Hamilton West
  "L9B": [43.2200, -79.9100],   // Ancaster
  "L9C": [43.2200, -79.8800],   // Hamilton Mountain
  "L9G": [43.2300, -79.9300],   // Dundas
  "L9H": [43.2700, -79.9200],   // Dundas
  "L9K": [43.2000, -79.9500],   // Ancaster

  // Southern/Southwestern Ontario — N prefix
  "N1E": [43.5400, -80.2500],   // Guelph
  "N1G": [43.5300, -80.2300],   // Guelph
  "N1H": [43.5500, -80.2500],   // Guelph
  "N1K": [43.5200, -80.2800],   // Guelph
  "N1L": [43.5600, -80.2700],   // Guelph
  "N1R": [43.4300, -80.3100],   // Cambridge
  "N1S": [43.4200, -80.3200],   // Cambridge
  "N1T": [43.4100, -80.3100],   // Cambridge
  "N2A": [43.4300, -80.4200],   // Kitchener
  "N2B": [43.4500, -80.4800],   // Kitchener
  "N2C": [43.4200, -80.4500],   // Kitchener
  "N2E": [43.4100, -80.4600],   // Kitchener
  "N2G": [43.4500, -80.4800],   // Kitchener
  "N2H": [43.4500, -80.4900],   // Kitchener
  "N2J": [43.4600, -80.5200],   // Waterloo
  "N2K": [43.4700, -80.5000],   // Waterloo
  "N2L": [43.4700, -80.5300],   // Waterloo
  "N2M": [43.4300, -80.4700],   // Kitchener
  "N2N": [43.4600, -80.4500],   // Kitchener
  "N2P": [43.4200, -80.5000],   // Kitchener
  "N2R": [43.4000, -80.4400],   // Kitchener
  "N2T": [43.4800, -80.5500],   // Waterloo
  "N2V": [43.5000, -80.5400],   // Waterloo
  "N5A": [43.0600, -80.7500],   // Woodstock
  "N5V": [43.0200, -81.2200],   // London
  "N5W": [43.0000, -81.2500],   // London
  "N5X": [43.0300, -81.2800],   // London
  "N5Y": [43.0100, -81.2600],   // London
  "N5Z": [43.0000, -81.2400],   // London
  "N6A": [43.0100, -81.2700],   // London
  "N6B": [42.9900, -81.2500],   // London
  "N6C": [42.9700, -81.2400],   // London
  "N6E": [42.9500, -81.2300],   // London
  "N6G": [43.0000, -81.2900],   // London
  "N6H": [42.9800, -81.3000],   // London
  "N6J": [42.9700, -81.2700],   // London
  "N6K": [42.9800, -81.3100],   // London
  "N8N": [42.3200, -82.9400],   // Tecumseh
  "N8P": [42.3100, -82.9600],   // Tecumseh
  "N8R": [42.3000, -82.9800],   // Windsor
  "N8S": [42.2900, -83.0000],   // Windsor
  "N8T": [42.3200, -83.0200],   // Windsor
  "N8W": [42.3000, -83.0400],   // Windsor
  "N8X": [42.3000, -83.0600],   // Windsor
  "N8Y": [42.3200, -83.0500],   // Windsor
  "N9A": [42.3200, -83.0400],   // Windsor
  "N9B": [42.3000, -83.0700],   // Windsor
  "N9C": [42.2800, -83.0600],   // Windsor
  "N9E": [42.2600, -83.0200],   // Windsor
  "N9G": [42.2700, -83.0800],   // Windsor
  "N9H": [42.2500, -83.0500],   // LaSalle
  "N9J": [42.2600, -83.0700],   // LaSalle
  "N9K": [42.2300, -82.9800],   // Amherstburg
  "N9V": [42.0500, -82.7500],   // Leamington
  "N9Y": [42.1000, -82.8500],   // Kingsville

  // Northern Ontario — P prefix
  "P1A": [46.4900, -80.9900],   // North Bay
  "P1B": [46.3300, -79.4700],   // Sturgeon Falls
  "P1C": [46.3200, -79.4500],   // North Bay
  "P1H": [45.3900, -79.2200],   // Huntsville
  "P1L": [44.7400, -79.8800],   // Orillia
  "P1P": [44.6200, -79.6200],   // Barrie
  "P2N": [48.4800, -89.2400],   // Thunder Bay
  "P3A": [46.4800, -81.0000],   // Sudbury
  "P3B": [46.5300, -80.9600],   // Sudbury
  "P3C": [46.4900, -81.0100],   // Sudbury
  "P3E": [46.4800, -80.9900],   // Sudbury
  "P3G": [46.5200, -81.0500],   // Sudbury
  "P3L": [46.5000, -81.0200],   // Sudbury
  "P3N": [46.5100, -80.9700],   // Sudbury
  "P3P": [46.4700, -80.9500],   // Sudbury
  "P3Y": [46.5200, -80.9400],   // Sudbury
  "P5A": [46.5100, -80.9800],   // Sudbury
  "P5E": [46.5200, -80.8800],   // Sudbury
  "P6A": [46.5300, -84.3500],   // Sault Ste Marie
  "P6B": [46.5200, -84.3300],   // Sault Ste Marie
  "P6C": [46.5400, -84.3200],   // Sault Ste Marie
  "P7A": [48.3900, -89.2500],   // Thunder Bay
  "P7B": [48.4100, -89.2400],   // Thunder Bay
  "P7C": [48.4200, -89.2700],   // Thunder Bay
  "P7E": [48.4300, -89.2800],   // Thunder Bay
  "P7G": [48.4400, -89.3200],   // Thunder Bay
  "P7J": [48.4000, -89.2300],   // Thunder Bay
  "P7K": [48.4000, -89.2100],   // Thunder Bay

  // Quebec — G (East), H (Montreal), J (West/North)
  "G1A": [46.8100, -71.2100],   // Quebec City
  "G1B": [46.8500, -71.1700],   // Beauport
  "G1C": [46.8700, -71.1500],   // Beauport
  "G1E": [46.8600, -71.1000],   // Beauport
  "G1G": [46.8500, -71.2500],   // Charlesbourg
  "G1H": [46.8600, -71.2800],   // Charlesbourg
  "G1J": [46.8200, -71.2100],   // Limoilou
  "G1K": [46.8100, -71.2200],   // Saint-Roch
  "G1L": [46.8200, -71.2200],   // Limoilou
  "G1M": [46.8000, -71.2500],   // Saint-Sauveur
  "G1N": [46.7900, -71.2700],   // Sainte-Foy
  "G1P": [46.7800, -71.2900],   // Sainte-Foy
  "G1R": [46.8100, -71.2100],   // Old Quebec
  "G1S": [46.7900, -71.2300],   // Sillery
  "G1T": [46.7800, -71.3200],   // Sainte-Foy
  "G1V": [46.7900, -71.2800],   // Sainte-Foy
  "G1W": [46.7700, -71.2600],   // Sainte-Foy
  "G1X": [46.7600, -71.3000],   // Sainte-Foy
  "G2A": [46.8800, -71.3200],   // Charlesbourg
  "G2B": [46.8900, -71.3000],   // Charlesbourg
  "G2C": [46.9100, -71.2800],   // Charlesbourg
  "G2E": [46.8300, -71.3200],   // Saint-Emile
  "G2G": [46.8500, -71.3400],   // Val-Belair
  "G2J": [46.8800, -71.2200],   // Beauport
  "G2K": [46.9100, -71.2600],   // Charlesbourg
  "G2L": [46.9200, -71.2400],   // Charlesbourg
  "G2N": [46.9000, -71.2000],   // Beauport

  // Montreal
  "H1A": [45.5700, -73.5200],   // Pointe-aux-Trembles
  "H1B": [45.5900, -73.5100],   // Montreal East
  "H1C": [45.6000, -73.5300],   // Riviere des Prairies
  "H1E": [45.6100, -73.5700],   // Riviere des Prairies
  "H1G": [45.5900, -73.6000],   // Montreal North
  "H1H": [45.5700, -73.6300],   // Montreal North
  "H1J": [45.5800, -73.5500],   // Anjou
  "H1K": [45.5700, -73.5600],   // Anjou
  "H1L": [45.5800, -73.5400],   // Anjou
  "H1M": [45.5500, -73.5500],   // Mercier
  "H1N": [45.5400, -73.5800],   // Hochelaga
  "H1P": [45.6000, -73.5900],   // Saint-Leonard
  "H1R": [45.5800, -73.5800],   // Saint-Leonard
  "H1S": [45.5700, -73.5900],   // Saint-Leonard
  "H1T": [45.5500, -73.6000],   // Rosemont
  "H1V": [45.5500, -73.5500],   // Mercier
  "H1W": [45.5400, -73.5700],   // Hochelaga
  "H1X": [45.5400, -73.5900],   // Rosemont
  "H1Y": [45.5300, -73.5800],   // Rosemont
  "H1Z": [45.5400, -73.6100],   // Villeray
  "H2A": [45.5400, -73.5800],   // Rosemont
  "H2B": [45.5500, -73.6300],   // Ahuntsic
  "H2C": [45.5400, -73.6400],   // Ahuntsic
  "H2E": [45.5400, -73.6200],   // Villeray
  "H2G": [45.5300, -73.5800],   // Rosemont
  "H2H": [45.5200, -73.5800],   // Plateau
  "H2J": [45.5300, -73.5700],   // Plateau
  "H2K": [45.5200, -73.5500],   // Centre-Sud
  "H2L": [45.5200, -73.5600],   // Plateau
  "H2M": [45.5500, -73.6500],   // Ahuntsic
  "H2N": [45.5500, -73.6300],   // Ahuntsic
  "H2P": [45.5400, -73.6400],   // Parc Extension
  "H2R": [45.5300, -73.6200],   // Villeray
  "H2S": [45.5400, -73.6000],   // Rosemont
  "H2T": [45.5200, -73.5900],   // Plateau
  "H2V": [45.5200, -73.6100],   // Outremont
  "H2W": [45.5100, -73.5800],   // Plateau
  "H2X": [45.5100, -73.5700],   // Milton-Parc
  "H2Y": [45.5100, -73.5600],   // Old Montreal
  "H2Z": [45.5100, -73.5600],   // Chinatown
  "H3A": [45.5000, -73.5800],   // McGill
  "H3B": [45.5000, -73.5700],   // Downtown
  "H3C": [45.4900, -73.5600],   // Griffintown
  "H3E": [45.4700, -73.5200],   // Ile des Soeurs
  "H3G": [45.5000, -73.5800],   // Downtown
  "H3H": [45.4900, -73.5800],   // Shaughnessy Village
  "H3J": [45.4900, -73.5800],   // Little Burgundy
  "H3K": [45.4800, -73.5600],   // Pointe-Saint-Charles
  "H3L": [45.5600, -73.6500],   // Ahuntsic
  "H3M": [45.5500, -73.7000],   // Cartierville
  "H3N": [45.5500, -73.6600],   // Ahuntsic
  "H3P": [45.5100, -73.6600],   // Mount Royal
  "H3R": [45.5000, -73.6200],   // NDG
  "H3S": [45.5100, -73.6300],   // Cote-des-Neiges
  "H3T": [45.5100, -73.6400],   // Cote-des-Neiges
  "H3V": [45.5100, -73.6100],   // Outremont
  "H3W": [45.4900, -73.6400],   // Cote-des-Neiges
  "H3X": [45.4800, -73.6400],   // Hampstead
  "H3Y": [45.4900, -73.5900],   // Westmount
  "H3Z": [45.4900, -73.6000],   // Westmount
  "H4A": [45.4800, -73.6100],   // NDG
  "H4B": [45.4700, -73.6300],   // Loyola
  "H4C": [45.4700, -73.5800],   // Saint-Henri
  "H4E": [45.4700, -73.5700],   // Verdun
  "H4G": [45.4700, -73.5700],   // Verdun
  "H4H": [45.4700, -73.5900],   // Verdun
  "H4J": [45.5600, -73.7000],   // Saint-Laurent
  "H4K": [45.5300, -73.6900],   // Saint-Laurent
  "H4L": [45.5200, -73.6800],   // Saint-Laurent
  "H4M": [45.5300, -73.7100],   // Saint-Laurent
  "H4N": [45.5200, -73.6800],   // Saint-Laurent
  "H4P": [45.5000, -73.6500],   // Cote-Saint-Luc
  "H4R": [45.5100, -73.7000],   // Saint-Laurent
  "H4S": [45.5100, -73.6800],   // Saint-Laurent
  "H4T": [45.5000, -73.6700],   // Mount Royal
  "H4V": [45.4700, -73.6200],   // NDG
  "H4W": [45.4800, -73.6300],   // Cote-Saint-Luc
  "H4X": [45.4600, -73.6300],   // NDG
  "H8N": [45.4500, -73.7400],   // LaSalle
  "H8P": [45.4400, -73.7600],   // LaSalle
  "H8R": [45.4500, -73.7200],   // LaSalle
  "H8S": [45.4300, -73.7000],   // Lachine
  "H8T": [45.4500, -73.7500],   // Dorval
  "H8Y": [45.4600, -73.7800],   // Dorval
  "H8Z": [45.4500, -73.7400],   // Dorval
  "H9A": [45.4800, -73.7600],   // Sainte-Anne-de-Bellevue
  "H9B": [45.4500, -73.8200],   // Pierrefonds
  "H9C": [45.4600, -73.8400],   // Pierrefonds
  "H9E": [45.4700, -73.8600],   // Sainte-Genevieve
  "H9G": [45.4800, -73.8300],   // Sainte-Genevieve
  "H9H": [45.4700, -73.8500],   // Pierrefonds
  "H9J": [45.5000, -73.8500],   // Pierrefonds
  "H9K": [45.5100, -73.8800],   // Ile-Bizard
  "H9R": [45.4700, -73.8000],   // Pointe-Claire
  "H9S": [45.4700, -73.7800],   // Pointe-Claire
  "H9W": [45.4900, -73.8000],   // Kirkland
  "H9X": [45.4700, -73.9400],   // Sainte-Anne-de-Bellevue

  // Quebec West/North — J prefix
  "J1E": [45.4000, -71.8900],   // Sherbrooke
  "J1G": [45.4100, -71.9200],   // Sherbrooke
  "J1H": [45.4000, -71.8800],   // Sherbrooke
  "J1J": [45.3900, -71.8800],   // Sherbrooke
  "J1K": [45.3800, -71.9200],   // Sherbrooke
  "J1L": [45.3800, -71.8600],   // Sherbrooke
  "J1M": [45.3700, -71.8500],   // Sherbrooke
  "J1N": [45.4100, -71.9400],   // Sherbrooke
  "J1R": [45.4000, -71.8700],   // Sherbrooke
  "J2S": [45.5000, -73.3000],   // Saint-Hyacinthe
  "J4B": [45.5300, -73.4600],   // Longueuil
  "J4G": [45.5200, -73.4700],   // Longueuil
  "J4H": [45.5300, -73.5000],   // Longueuil
  "J4J": [45.5400, -73.4700],   // Longueuil
  "J4K": [45.5100, -73.4600],   // Longueuil
  "J4L": [45.5000, -73.4800],   // Saint-Lambert
  "J4N": [45.5000, -73.4700],   // Longueuil
  "J4P": [45.5000, -73.5000],   // Greenfield Park
  "J4R": [45.4900, -73.5200],   // Greenfield Park
  "J4S": [45.4900, -73.4600],   // Saint-Hubert
  "J4T": [45.5100, -73.4500],   // Longueuil
  "J4V": [45.5000, -73.4500],   // Saint-Hubert
  "J4W": [45.4800, -73.5100],   // Saint-Lambert
  "J4X": [45.4700, -73.4900],   // Saint-Lambert
  "J4Y": [45.4900, -73.4400],   // Saint-Hubert
  "J4Z": [45.4700, -73.4200],   // Saint-Hubert
  "J5A": [45.4500, -73.4000],   // Saint-Hubert
  "J5R": [45.3700, -73.3100],   // Chambly
  "J6E": [46.0200, -73.4300],   // Joliette
  "J6S": [45.5500, -73.8000],   // Laval
  "J6T": [45.5600, -73.7800],   // Laval
  "J6V": [45.5600, -73.7300],   // Laval
  "J6W": [45.5800, -73.7600],   // Laval
  "J6X": [45.5700, -73.7100],   // Laval
  "J6Y": [45.5900, -73.7100],   // Laval
  "J6Z": [45.6000, -73.7500],   // Laval
  "J7A": [45.5700, -73.7500],   // Laval
  "J7B": [45.6100, -73.8000],   // Laval
  "J7C": [45.5800, -73.7300],   // Laval
  "J7E": [45.5600, -73.7500],   // Laval
  "J7G": [45.5200, -73.7500],   // Laval
  "J7H": [45.5300, -73.7400],   // Laval
  "J7K": [45.5300, -73.7700],   // Laval
  "J7L": [45.5400, -73.7800],   // Laval
  "J7M": [45.5100, -73.7500],   // Laval
  "J7N": [45.5300, -73.7100],   // Laval
  "J7P": [45.5200, -73.7900],   // Laval
  "J7R": [45.5400, -73.7500],   // Laval
  "J7T": [45.5700, -73.8200],   // Laval
  "J7V": [45.5800, -73.8300],   // Laval
  "J7W": [45.5100, -73.7200],   // Laval
  "J7X": [45.5800, -73.7800],   // Laval
  "J7Y": [45.5600, -73.7500],   // Laval
  "J7Z": [45.5800, -74.0000],   // Saint-Eustache
  "J8P": [45.4800, -75.4700],   // Gatineau
  "J8R": [45.4900, -75.4600],   // Gatineau
  "J8T": [45.4600, -75.5000],   // Gatineau
  "J8V": [45.4700, -75.7300],   // Gatineau
  "J8X": [45.4500, -75.7200],   // Gatineau
  "J8Y": [45.4400, -75.7300],   // Gatineau
  "J8Z": [45.4500, -75.7400],   // Gatineau
  "J9A": [45.4400, -75.7500],   // Gatineau
  "J9B": [45.4300, -75.7200],   // Gatineau
  "J9H": [45.4700, -75.8000],   // Aylmer
  "J9J": [45.4800, -75.7800],   // Aylmer

  // Alberta
  "T1X": [51.0800, -113.9800],  // Chestermere
  "T1Y": [51.0900, -113.9500],  // Calgary NE
  "T2A": [51.0500, -113.9600],  // Forest Lawn
  "T2B": [51.0300, -113.9500],  // Forest Heights
  "T2C": [50.9900, -114.0100],  // Ogden
  "T2E": [51.0800, -114.0400],  // Calgary N
  "T2G": [51.0400, -114.0500],  // Inglewood
  "T2H": [51.0200, -114.0600],  // Manchester
  "T2J": [50.9800, -114.0400],  // Willow Park
  "T2K": [51.0900, -114.0800],  // Highland Park
  "T2L": [51.1000, -114.1100],  // Banff Trail
  "T2M": [51.0800, -114.0900],  // Mount Pleasant
  "T2N": [51.0600, -114.0800],  // Hillhurst
  "T2P": [51.0500, -114.0700],  // Downtown
  "T2R": [51.0400, -114.0800],  // Beltline
  "T2S": [51.0300, -114.0600],  // Mission
  "T2T": [51.0300, -114.0800],  // South Calgary
  "T2V": [50.9900, -114.0700],  // Haysboro
  "T2W": [50.9700, -114.0800],  // Woodlands
  "T2X": [50.9500, -114.0500],  // McKenzie
  "T2Y": [50.9300, -114.1000],  // Shawnessy
  "T2Z": [50.9300, -113.9700],  // Auburn Bay
  "T3A": [51.1200, -114.1600],  // Charleswood
  "T3B": [51.0900, -114.1800],  // Bowness
  "T3C": [51.0400, -114.1100],  // Killarney
  "T3E": [51.0200, -114.1200],  // Lakeview
  "T3G": [51.1500, -114.1300],  // Tuscany
  "T3H": [51.0500, -114.1800],  // Aspen Woods
  "T3J": [51.1200, -114.0400],  // Martindale
  "T3K": [51.1500, -114.0500],  // Harvest Hills
  "T3L": [51.1400, -114.1800],  // Rocky Ridge
  "T3M": [50.8800, -114.0600],  // Okotoks
  "T3N": [51.0100, -114.1600],  // West Springs
  "T3P": [51.0700, -114.2000],  // Coach Hill
  "T3R": [51.1300, -114.2200],  // Bearspaw
  "T3S": [50.9000, -113.9600],  // De Winton
  "T3Z": [51.0800, -114.7600],  // Cochrane
  "T4N": [52.2700, -113.8100],  // Red Deer
  "T4P": [52.2800, -113.8000],  // Red Deer
  "T4R": [52.2500, -113.8200],  // Red Deer
  "T5A": [53.5900, -113.4100],  // Clareview
  "T5B": [53.5700, -113.4600],  // McCauley
  "T5C": [53.5700, -113.4300],  // Eastwood
  "T5E": [53.5900, -113.5200],  // Northmount
  "T5G": [53.5700, -113.5000],  // Prince Rupert
  "T5H": [53.5500, -113.4900],  // Oliver
  "T5J": [53.5400, -113.4900],  // Downtown
  "T5K": [53.5500, -113.5100],  // Oliver
  "T5L": [53.5800, -113.5300],  // Calder
  "T5M": [53.5700, -113.5400],  // Inglewood
  "T5N": [53.5600, -113.5300],  // Woodcroft
  "T5P": [53.5600, -113.5600],  // Jasper Place
  "T5R": [53.5500, -113.5500],  // Crestwood
  "T5S": [53.5700, -113.6000],  // Winterburn
  "T5T": [53.5400, -113.6300],  // Lewis Farms
  "T5V": [53.5900, -113.5700],  // Winterburn
  "T5W": [53.5500, -113.4200],  // Capilano
  "T5X": [53.6000, -113.4800],  // Dunluce
  "T5Y": [53.6100, -113.4100],  // Clareview
  "T5Z": [53.6200, -113.5200],  // Elsinore
  "T6A": [53.5400, -113.4500],  // Bonnie Doon
  "T6B": [53.5300, -113.4200],  // Terrace Heights
  "T6C": [53.5300, -113.4600],  // Strathearn
  "T6E": [53.5200, -113.4900],  // Strathcona
  "T6G": [53.5200, -113.5200],  // University
  "T6H": [53.5000, -113.5200],  // Belgravia
  "T6J": [53.4800, -113.4900],  // Pleasantview
  "T6K": [53.4700, -113.4400],  // Mill Woods
  "T6L": [53.4600, -113.4200],  // Mill Woods
  "T6M": [53.5200, -113.5700],  // Glenora
  "T6N": [53.4600, -113.4800],  // Terwillegar
  "T6P": [53.5400, -113.3600],  // Sherwood Park
  "T6R": [53.4800, -113.5500],  // Riverbend
  "T6S": [53.5100, -113.3200],  // Sherwood Park
  "T6T": [53.4500, -113.3800],  // Sherwood Park
  "T6V": [53.5600, -113.3600],  // Sherwood Park
  "T6W": [53.4400, -113.5100],  // Terwillegar
  "T6X": [53.4200, -113.4900],  // Ellerslie
  "T8A": [53.5600, -113.3100],  // Sherwood Park
  "T8H": [53.5300, -113.3100],  // Sherwood Park
  "T8N": [53.6000, -113.6500],  // St. Albert
  "T8R": [53.5100, -113.6000],  // Spruce Grove
  "T8T": [53.5200, -113.5800],  // Stony Plain
  "T8V": [53.5400, -113.7200],  // Spruce Grove
  "T9E": [53.2700, -113.5700],  // Leduc

  // British Columbia
  "V1A": [50.7300, -116.0700],  // Invermere
  "V1C": [49.9100, -119.4800],  // Kelowna
  "V1G": [56.2400, -120.8500],  // Dawson Creek
  "V1H": [50.3600, -119.3400],  // Vernon
  "V1K": [50.6800, -120.3300],  // Kamloops
  "V1L": [49.3200, -117.6500],  // Nelson
  "V1N": [49.5000, -117.3000],  // Castlegar
  "V1S": [50.6900, -120.3700],  // Kamloops
  "V1T": [50.6700, -120.3200],  // Kamloops
  "V1V": [49.8600, -119.3500],  // Kelowna
  "V1W": [49.8700, -119.4200],  // Kelowna
  "V1X": [49.8800, -119.4500],  // Kelowna
  "V1Y": [49.8800, -119.4800],  // Kelowna
  "V1Z": [49.9200, -119.5000],  // West Kelowna
  "V2A": [49.5000, -119.5800],  // Penticton
  "V2B": [50.6800, -120.3800],  // Kamloops
  "V2C": [50.6800, -120.3500],  // Kamloops
  "V2E": [50.7000, -120.4200],  // Kamloops
  "V2G": [52.1500, -122.1400],  // Williams Lake
  "V2H": [50.7100, -120.3600],  // Kamloops
  "V2J": [54.7500, -126.9500],  // Burns Lake
  "V2N": [53.9100, -122.7500],  // Prince George
  "V2V": [49.2100, -122.6000],  // Maple Ridge
  "V3A": [49.2100, -122.9100],  // New Westminster
  "V3B": [49.2700, -122.7900],  // Port Coquitlam
  "V3C": [49.2600, -122.7600],  // Port Coquitlam
  "V3E": [49.2200, -122.7500],  // Port Coquitlam
  "V3H": [49.2800, -122.8500],  // Port Moody
  "V3J": [49.2700, -122.8000],  // Coquitlam
  "V3K": [49.2700, -122.8200],  // Coquitlam
  "V3L": [49.2000, -122.9100],  // New Westminster
  "V3M": [49.2100, -122.9200],  // New Westminster
  "V3N": [49.2200, -122.9300],  // Burnaby
  "V3R": [49.2000, -122.8500],  // Surrey
  "V3S": [49.1700, -122.7600],  // Surrey
  "V3T": [49.1900, -122.8700],  // Surrey
  "V3V": [49.2000, -122.8800],  // Surrey
  "V3W": [49.1500, -122.8100],  // Surrey
  "V3X": [49.1500, -122.8400],  // Surrey
  "V4A": [49.0300, -122.8400],  // White Rock
  "V4C": [49.1700, -122.8900],  // Surrey
  "V4E": [49.0800, -122.8100],  // Surrey
  "V4G": [49.1000, -122.7900],  // Surrey
  "V4K": [49.0900, -122.7300],  // Surrey
  "V4N": [49.1800, -122.7300],  // Surrey
  "V4P": [49.0500, -122.8300],  // White Rock
  "V5A": [49.2700, -122.9700],  // Burnaby North
  "V5B": [49.2800, -122.9500],  // Burnaby
  "V5C": [49.2800, -122.9900],  // Burnaby
  "V5E": [49.2100, -122.9600],  // Burnaby
  "V5G": [49.2500, -122.9600],  // Burnaby
  "V5H": [49.2200, -122.9800],  // Burnaby
  "V5J": [49.2200, -123.0000],  // Burnaby
  "V5K": [49.2800, -123.0200],  // Vancouver
  "V5L": [49.2700, -123.0700],  // Vancouver
  "V5M": [49.2600, -123.0500],  // Vancouver
  "V5N": [49.2500, -123.0600],  // Vancouver
  "V5P": [49.2300, -123.0500],  // Vancouver
  "V5R": [49.2400, -123.0200],  // Vancouver
  "V5S": [49.2200, -123.0100],  // Vancouver
  "V5T": [49.2600, -123.1000],  // Vancouver
  "V5V": [49.2500, -123.0900],  // Vancouver
  "V5W": [49.2300, -123.0900],  // Vancouver
  "V5X": [49.2200, -123.0800],  // Vancouver
  "V5Y": [49.2600, -123.1100],  // Vancouver
  "V5Z": [49.2500, -123.1100],  // Vancouver
  "V6A": [49.2800, -123.0900],  // Strathcona
  "V6B": [49.2800, -123.1200],  // Downtown
  "V6C": [49.2900, -123.1200],  // Coal Harbour
  "V6E": [49.2800, -123.1300],  // West End
  "V6G": [49.2900, -123.1400],  // West End
  "V6H": [49.2600, -123.1300],  // Fairview
  "V6J": [49.2600, -123.1400],  // Kitsilano
  "V6K": [49.2700, -123.1500],  // Kitsilano
  "V6L": [49.2500, -123.1600],  // Kerrisdale
  "V6M": [49.2400, -123.1400],  // Riley Park
  "V6N": [49.2400, -123.1700],  // Dunbar
  "V6P": [49.2200, -123.1400],  // Marpole
  "V6R": [49.2700, -123.1700],  // Point Grey
  "V6S": [49.2600, -123.1700],  // Kerrisdale
  "V6T": [49.2700, -123.2500],  // UBC
  "V6Z": [49.2800, -123.1200],  // Downtown South
  "V7G": [49.3300, -122.9400],  // Deep Cove
  "V7H": [49.3100, -122.9600],  // North Vancouver
  "V7J": [49.3200, -123.0100],  // North Vancouver
  "V7K": [49.3200, -123.0200],  // North Vancouver
  "V7L": [49.3200, -123.0300],  // North Vancouver
  "V7M": [49.3100, -123.0600],  // North Vancouver
  "V7N": [49.3300, -123.0400],  // North Vancouver
  "V7P": [49.3200, -123.0800],  // North Vancouver
  "V7R": [49.3400, -123.1000],  // North Vancouver
  "V7S": [49.3500, -123.2000],  // West Vancouver
  "V7T": [49.3400, -123.1600],  // West Vancouver
  "V7V": [49.3300, -123.1600],  // West Vancouver
  "V7W": [49.3400, -123.2500],  // West Vancouver
  "V8A": [48.9200, -123.7500],  // Ladysmith
  "V8K": [48.8500, -123.5000],  // Salt Spring Island
  "V8L": [48.6500, -123.4100],  // Sidney
  "V8N": [48.4400, -123.3200],  // Victoria
  "V8P": [48.4300, -123.3400],  // Victoria
  "V8R": [48.4300, -123.3200],  // Victoria
  "V8S": [48.4200, -123.3300],  // Victoria
  "V8T": [48.4400, -123.3600],  // Victoria
  "V8V": [48.4300, -123.3700],  // Victoria
  "V8W": [48.4200, -123.3600],  // Victoria Downtown
  "V8X": [48.4500, -123.3700],  // Saanich
  "V8Y": [48.4600, -123.4200],  // Royal Oak
  "V8Z": [48.4600, -123.3800],  // Saanich
  "V9A": [48.4300, -123.3900],  // Esquimalt
  "V9B": [48.4500, -123.4400],  // Colwood
  "V9C": [48.4400, -123.4900],  // Colwood
  "V9E": [48.5000, -123.3900],  // Saanich
  "V9R": [49.1700, -123.9400],  // Nanaimo
  "V9S": [49.1600, -123.9600],  // Nanaimo
  "V9T": [49.1800, -123.9500],  // Nanaimo
  "V9V": [49.2000, -124.0000],  // Nanaimo
  "V9X": [48.8600, -123.7400],  // Duncan

  // Manitoba
  "R0A": [50.0000, -96.5000],   // Eastern Manitoba
  "R0B": [51.0000, -97.0000],   // Northern Manitoba
  "R0C": [50.5000, -97.0000],   // Central Manitoba
  "R0E": [50.0000, -96.0000],   // Southeast Manitoba
  "R0G": [49.5000, -98.0000],   // SW Manitoba
  "R0H": [50.5000, -99.0000],   // West Central Manitoba
  "R0J": [50.5000, -100.0000],  // Western Manitoba
  "R0K": [49.5000, -99.0000],   // Southwestern Manitoba
  "R0L": [51.5000, -100.0000],  // Northwest Manitoba
  "R0M": [49.8000, -101.0000],  // SW Manitoba
  "R2C": [49.8950, -97.0400],   // Winnipeg
  "R2G": [49.9300, -97.0700],   // Winnipeg
  "R2H": [49.8700, -97.1100],   // Winnipeg
  "R2J": [49.8600, -97.0800],   // Winnipeg
  "R2K": [49.9200, -97.0800],   // Winnipeg
  "R2L": [49.9100, -97.1000],   // Winnipeg
  "R2M": [49.8500, -97.1100],   // Winnipeg
  "R2N": [49.8400, -97.1000],   // Winnipeg
  "R2P": [49.9200, -97.1500],   // Winnipeg
  "R2R": [49.9100, -97.2100],   // Winnipeg
  "R2V": [49.9300, -97.1400],   // Winnipeg
  "R2W": [49.9100, -97.1000],   // Winnipeg
  "R2X": [49.9300, -97.1400],   // Winnipeg
  "R2Y": [49.8800, -97.2500],   // Charleswood
  "R3A": [49.8900, -97.1500],   // Downtown
  "R3B": [49.8900, -97.1500],   // Downtown
  "R3C": [49.8800, -97.1500],   // Downtown
  "R3E": [49.9000, -97.1600],   // West Kildonan
  "R3G": [49.8900, -97.1700],   // Wolseley
  "R3H": [49.8800, -97.1800],   // Winnipeg
  "R3J": [49.8700, -97.2300],   // St. James
  "R3K": [49.8800, -97.2700],   // St. James
  "R3L": [49.8700, -97.1400],   // River Heights
  "R3M": [49.8600, -97.1600],   // River Heights
  "R3N": [49.8700, -97.1800],   // Wolseley
  "R3P": [49.8500, -97.2000],   // Fort Garry
  "R3R": [49.8600, -97.2500],   // Charleswood
  "R3S": [49.8300, -97.2300],   // Fort Garry
  "R3T": [49.8400, -97.1700],   // Fort Garry
  "R3V": [49.8200, -97.1400],   // St. Vital
  "R3W": [49.8300, -97.0900],   // St. Vital
  "R3X": [49.8100, -97.1000],   // St. Vital
  "R3Y": [49.8300, -97.2400],   // Linden Woods
  "R7A": [49.8500, -99.9500],   // Brandon
  "R7B": [49.8500, -99.9300],   // Brandon
  "R7C": [49.8300, -99.9500],   // Brandon

  // Saskatchewan
  "S0A": [50.5000, -102.0000],  // SE Saskatchewan
  "S0C": [49.5000, -103.0000],  // SE Saskatchewan
  "S0E": [52.0000, -104.0000],  // East Central Sask
  "S0G": [50.5000, -105.0000],  // Central Saskatchewan
  "S0H": [50.0000, -107.0000],  // SW Saskatchewan
  "S0J": [52.0000, -107.0000],  // NW Saskatchewan
  "S0K": [52.5000, -105.0000],  // North Central Sask
  "S0L": [51.5000, -108.0000],  // West Central Sask
  "S0M": [53.0000, -109.0000],  // NW Saskatchewan
  "S0N": [49.5000, -109.0000],  // SW Saskatchewan
  "S0P": [54.0000, -105.0000],  // Northern Saskatchewan
  "S4L": [50.4600, -104.5700],  // Regina
  "S4N": [50.4500, -104.5800],  // Regina
  "S4P": [50.4500, -104.6100],  // Regina
  "S4R": [50.4700, -104.6200],  // Regina
  "S4S": [50.4200, -104.5900],  // Regina
  "S4T": [50.4500, -104.6400],  // Regina
  "S4V": [50.4300, -104.5600],  // Regina
  "S4W": [50.4600, -104.6000],  // Regina
  "S4X": [50.4800, -104.6200],  // Regina
  "S4Y": [50.4700, -104.5700],  // Regina
  "S4Z": [50.4600, -104.5600],  // Regina
  "S7H": [52.1300, -106.6700],  // Saskatoon
  "S7J": [52.1100, -106.6600],  // Saskatoon
  "S7K": [52.1500, -106.6700],  // Saskatoon
  "S7L": [52.1400, -106.6900],  // Saskatoon
  "S7M": [52.1300, -106.7000],  // Saskatoon
  "S7N": [52.1400, -106.6400],  // Saskatoon
  "S7P": [52.1600, -106.6400],  // Saskatoon
  "S7R": [52.1700, -106.6800],  // Saskatoon
  "S7S": [52.1700, -106.7100],  // Saskatoon
  "S7T": [52.1200, -106.5900],  // Saskatoon
  "S7V": [52.1100, -106.6200],  // Saskatoon
  "S7W": [52.1100, -106.7200],  // Saskatoon

  // Nova Scotia
  "B2T": [44.7000, -63.6000],   // Fall River
  "B2V": [44.7300, -63.5700],   // Fall River
  "B2W": [44.6400, -63.4900],   // Cole Harbour
  "B2X": [44.6900, -63.5200],   // Dartmouth
  "B2Y": [44.6700, -63.5700],   // Dartmouth
  "B2Z": [44.6500, -63.5200],   // Eastern Passage
  "B3A": [44.6600, -63.5500],   // Dartmouth
  "B3B": [44.6800, -63.5700],   // Burnside
  "B3G": [44.7400, -63.6300],   // Fall River
  "B3H": [44.6400, -63.5800],   // Halifax
  "B3J": [44.6500, -63.5700],   // Halifax
  "B3K": [44.6500, -63.5800],   // Halifax
  "B3L": [44.6500, -63.5900],   // Halifax
  "B3M": [44.6800, -63.6400],   // Clayton Park
  "B3N": [44.6400, -63.6000],   // Armdale
  "B3P": [44.6200, -63.5800],   // Spryfield
  "B3R": [44.6100, -63.5900],   // Herring Cove
  "B3S": [44.6500, -63.6200],   // Bayers Lake
  "B3T": [44.6600, -63.6300],   // Kearney Lake
  "B3V": [44.6200, -63.5300],   // Halifax
  "B3Z": [44.6700, -63.5100],   // Lake Echo

  // New Brunswick
  "E1A": [46.0800, -64.7800],   // Moncton
  "E1B": [46.0900, -64.7700],   // Moncton
  "E1C": [46.0900, -64.7500],   // Moncton
  "E1E": [46.1000, -64.8000],   // Moncton
  "E1G": [46.1100, -64.8200],   // Moncton
  "E1H": [46.1000, -64.8400],   // Riverview
  "E2E": [45.9700, -66.6400],   // Fredericton
  "E2G": [45.9500, -66.6600],   // Fredericton
  "E2H": [45.9800, -66.6700],   // Fredericton
  "E2J": [45.9600, -66.6100],   // Fredericton
  "E2K": [45.9600, -66.6500],   // Fredericton
  "E2L": [45.2700, -66.0700],   // Saint John
  "E2M": [45.2800, -66.0900],   // Saint John
  "E2N": [45.2600, -66.0500],   // Saint John
  "E2P": [45.3000, -66.1000],   // Saint John
  "E2R": [45.2600, -66.0800],   // Saint John

  // Newfoundland
  "A1A": [47.5700, -52.7100],   // St. John's
  "A1B": [47.5700, -52.7300],   // St. John's
  "A1C": [47.5600, -52.7200],   // St. John's
  "A1E": [47.5500, -52.7400],   // St. John's
  "A1G": [47.5300, -52.7800],   // Mount Pearl
  "A1H": [47.5200, -52.8100],   // Paradise
  "A1N": [47.5100, -52.8400],   // Conception Bay South
  "A1S": [47.5000, -52.8700],   // Conception Bay South
  "A1V": [47.5600, -52.7000],   // St. John's
  "A1W": [47.5800, -52.7400],   // St. John's
  "A2N": [48.9500, -54.5700],   // Grand Falls-Windsor
  "A2V": [48.9400, -55.6600],   // Gander

  // PEI
  "C1A": [46.2400, -63.1300],   // Charlottetown
  "C1B": [46.2500, -63.1100],   // Charlottetown
  "C1C": [46.2600, -63.1000],   // Charlottetown
  "C1E": [46.2300, -63.1300],   // Charlottetown

  // Territories
  "X0A": [63.7500, -68.5200],   // Iqaluit (NU)
  "X0B": [64.5000, -89.0000],   // Baker Lake area (NU)
  "X0C": [69.4500, -133.0300],  // Inuvik area (NWT)
  "X0E": [62.4500, -114.3700],  // Yellowknife area (NWT)
  "X0G": [60.7200, -135.0500],  // Whitehorse area (YT)
  "X1A": [62.4500, -114.3700],  // Yellowknife
  "Y1A": [60.7200, -135.0500],  // Whitehorse
};

// ============================================================================
// Province prefix fallback coordinates
// ============================================================================

/**
 * Fallback centroids when FSA isn't in the lookup table.
 * Uses the first letter of the postal code (province indicator).
 */
const PROVINCE_FALLBACK = {
  "A": [47.56, -52.71],   // Newfoundland — St. John's
  "B": [44.65, -63.57],   // Nova Scotia — Halifax
  "C": [46.24, -63.13],   // PEI — Charlottetown
  "E": [46.09, -64.77],   // New Brunswick — Moncton
  "G": [46.81, -71.22],   // Eastern Quebec — Quebec City
  "H": [45.50, -73.57],   // Montreal area
  "J": [45.50, -73.60],   // Western Quebec — Montreal suburbs
  "K": [45.42, -75.70],   // Eastern Ontario — Ottawa
  "L": [43.70, -79.42],   // Central Ontario — Toronto
  "M": [43.65, -79.38],   // Metro Toronto
  "N": [43.00, -81.25],   // Southwestern Ontario — London
  "P": [46.49, -81.00],   // Northern Ontario — Sudbury
  "R": [49.90, -97.14],   // Manitoba — Winnipeg
  "S": [52.13, -106.67],  // Saskatchewan — Saskatoon
  "T": [51.05, -114.07],  // Alberta — Calgary
  "V": [49.28, -123.12],  // British Columbia — Vancouver
  "X": [62.45, -114.37],  // NWT/Nunavut — Yellowknife
  "Y": [60.72, -135.05],  // Yukon — Whitehorse
};

// ============================================================================
// Public API
// ============================================================================

/**
 * Look up approximate coordinates for a Canadian postal code.
 *
 * Tries exact FSA match first, then falls back to province centroid.
 *
 * @param {string} postalCode - Canadian postal code (e.g. "K1A 0B1" or "K1A0B1")
 * @returns {{ lat: number, lon: number, fsa: string, accuracy: string } | null}
 */
function postalToCoords(postalCode) {
  // Normalize: uppercase, remove spaces
  const code = (postalCode || "").toUpperCase().replace(/\s+/g, "");

  // Basic validation: Canadian postal code format is A1A1A1
  if (!/^[A-Z]\d[A-Z]/.test(code)) {
    return null;
  }

  const fsa = code.substring(0, 3);

  // Try exact FSA match
  if (FSA_COORDS[fsa]) {
    const [lat, lon] = FSA_COORDS[fsa];
    return { lat, lon, fsa, accuracy: "FSA (~5 km)" };
  }

  // Fall back to province letter
  const provinceLetter = code[0];
  if (PROVINCE_FALLBACK[provinceLetter]) {
    const [lat, lon] = PROVINCE_FALLBACK[provinceLetter];
    return { lat, lon, fsa, accuracy: "Province centroid (~100 km)" };
  }

  return null;
}

// ============================================================================
// Exports
// ============================================================================

if (typeof module !== "undefined" && module.exports) {
  module.exports = { postalToCoords, FSA_COORDS, PROVINCE_FALLBACK };
}
