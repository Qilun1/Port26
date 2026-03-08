-- Run in Supabase Dashboard -> SQL Editor
-- Populate sensors table with ~100 sensors in Helsinki region
-- March weather data: temperatures -5°C to +5°C, AQI 15-50

insert into public.sensors (
    sensor_code,
    name,
    latitude,
    longitude,
    latest_temperature_c,
    latest_air_pressure_hpa,
    latest_aqi
)
values
    -- City Center (Kamppi, Railway Station) - Dense coverage
    ('HEL-CENTER-001', 'Kamppi Center', 60.1688, 24.9319, 1.2, 1013.5, 32),
    ('HEL-CENTER-002', 'Railway Square', 60.1710, 24.9414, 1.5, 1013.8, 28),
    ('HEL-CENTER-003', 'Kluuvi Park', 60.1692, 24.9465, 1.3, 1013.2, 35),
    ('HEL-CENTER-004', 'Senaatintori', 60.1695, 24.9520, 0.9, 1014.1, 25),
    ('HEL-CENTER-005', 'Esplanadi West', 60.1675, 24.9425, 1.8, 1012.9, 38),
    ('HEL-CENTER-006', 'Mannerheimintie South', 60.1658, 24.9380, 1.4, 1013.6, 42),
    ('HEL-CENTER-007', 'Forum Shopping', 60.1682, 24.9375, 1.6, 1013.1, 36),
    ('HEL-CENTER-008', 'Stockmann Corner', 60.1686, 24.9440, 1.7, 1013.4, 30),
    ('HEL-CENTER-009', 'Kaisaniemi Park', 60.1725, 24.9445, 0.8, 1014.3, 22),
    ('HEL-CENTER-010', 'Hakaniemi Square', 60.1790, 24.9515, 0.5, 1014.8, 27),

    -- Kallio District - Dense coverage
    ('HEL-KALLIO-001', 'Kallio Church', 60.1841, 24.9506, 0.3, 1015.1, 24),
    ('HEL-KALLIO-002', 'Porthaninkatu', 60.1855, 24.9485, 0.2, 1015.3, 26),
    ('HEL-KALLIO-003', 'Fleminginkatu', 60.1875, 24.9520, -0.1, 1015.6, 23),
    ('HEL-KALLIO-004', 'Karhupuisto', 60.1825, 24.9548, 0.6, 1014.9, 29),
    ('HEL-KALLIO-005', 'Pengerkatu', 60.1890, 24.9495, -0.3, 1015.8, 21),
    ('HEL-KALLIO-006', 'Sörnäisten Rantatie', 60.1805, 24.9615, 0.8, 1014.5, 31),
    ('HEL-KALLIO-007', 'Alppila Park', 60.1920, 24.9525, -0.5, 1016.0, 19),

    -- Töölö - Moderate coverage
    ('HEL-TOOLO-001', 'Töölö Bay West', 60.1765, 24.9245, 1.1, 1013.7, 28),
    ('HEL-TOOLO-002', 'Hesperia Park', 60.1795, 24.9185, 0.9, 1014.0, 25),
    ('HEL-TOOLO-003', 'Sibelius Monument', 60.1825, 24.9125, 0.4, 1014.5, 22),
    ('HEL-TOOLO-004', 'Töölöntori', 60.1815, 24.9315, 1.0, 1013.9, 30),
    ('HEL-TOOLO-005', 'Eläintarhantie', 60.1885, 24.9275, 0.2, 1014.8, 26),
    ('HEL-TOOLO-006', 'Olympic Stadium', 60.1875, 24.9265, 0.3, 1014.6, 27),

    -- Punavuori - Moderate coverage
    ('HEL-PUNAVUORI-001', 'Vanha Kirkkopuisto', 60.1615, 24.9385, 2.1, 1012.8, 40),
    ('HEL-PUNAVUORI-002', 'Iso Roobertinkatu', 60.1605, 24.9435, 2.0, 1012.9, 38),
    ('HEL-PUNAVUORI-003', 'Tehtaankatu', 60.1590, 24.9325, 2.2, 1012.5, 42),
    ('HEL-PUNAVUORI-004', 'Eira Park', 60.1560, 24.9425, 2.4, 1012.3, 36),
    ('HEL-PUNAVUORI-005', 'Fredrikinkatu', 60.1635, 24.9365, 1.9, 1013.0, 39),

    -- Kruununhaka - Moderate coverage
    ('HEL-KRUUNUNHAKA-001', 'University Main Building', 60.1695, 24.9495, 1.0, 1013.9, 29),
    ('HEL-KRUUNUNHAKA-002', 'Ritarikatu', 60.1720, 24.9555, 0.7, 1014.2, 27),
    ('HEL-KRUUNUNHAKA-003', 'Tove Jansson Park', 60.1750, 24.9595, 0.5, 1014.5, 24),
    ('HEL-KRUUNUNHAKA-004', 'Tähtitorninkatu', 60.1735, 24.9505, 0.8, 1014.1, 28),

    -- Katajanokka
    ('HEL-KATAJANOKKA-001', 'Uspenski Cathedral', 60.1685, 24.9605, 1.3, 1013.4, 30),
    ('HEL-KATAJANOKKA-002', 'Katajanokanranta', 60.1645, 24.9685, 1.6, 1013.0, 33),
    ('HEL-KATAJANOKKA-003', 'Merikasarmi', 60.1655, 24.9745, 1.8, 1012.7, 35),

    -- Munkkiniemi - Sparser coverage
    ('HEL-MUNKKINIEMI-001', 'Munkkiniemen Puistotie', 60.2045, 24.8765, -1.2, 1016.5, 18),
    ('HEL-MUNKKINIEMI-002', 'Laaksolahti', 60.2015, 24.8685, -0.9, 1016.3, 20),
    ('HEL-MUNKKINIEMI-003', 'Meilahti Hospital', 60.1915, 24.8925, 0.1, 1015.2, 24),

    -- Lauttasaari - Moderate coverage
    ('HEL-LAUTTASAARI-001', 'Lauttasaari Metro', 60.1595, 24.8765, 1.5, 1013.2, 28),
    ('HEL-LAUTTASAARI-002', 'Myllykallio', 60.1545, 24.8685, 1.8, 1012.8, 30),
    ('HEL-LAUTTASAARI-003', 'Vattuniemi', 60.1495, 24.8585, 2.1, 1012.4, 32),
    ('HEL-LAUTTASAARI-004', 'Kotkavuori', 60.1625, 24.8825, 1.3, 1013.5, 26),

    -- Pasila - Moderate coverage
    ('HEL-PASILA-001', 'Pasila Station', 60.1985, 24.9335, -0.4, 1015.2, 34),
    ('HEL-PASILA-002', 'Ilmala', 60.2025, 24.9255, -0.7, 1015.5, 31),
    ('HEL-PASILA-003', 'Veturitori', 60.1995, 24.9295, -0.5, 1015.3, 33),
    ('HEL-PASILA-004', 'Keski-Pasila', 60.2005, 24.9385, -0.3, 1015.1, 32),

    -- Vallila
    ('HEL-VALLILA-001', 'Vallilan Vapaala', 60.1925, 24.9615, -0.2, 1015.0, 28),
    ('HEL-VALLILA-002', 'Hämeentie North', 60.1950, 24.9585, -0.4, 1015.2, 27),
    ('HEL-VALLILA-003', 'Kumpula Science Park', 60.2035, 24.9625, -0.8, 1015.7, 23),

    -- Herttoniemi
    ('HEL-HERTTONIEMI-001', 'Herttoniemi Metro', 60.1875, 25.0335, 0.2, 1014.6, 29),
    ('HEL-HERTTONIEMI-002', 'Linnanrakentajantie', 60.1915, 25.0285, -0.1, 1014.9, 27),
    ('HEL-HERTTONIEMI-003', 'Viikinranta', 60.1945, 25.0415, -0.3, 1015.1, 25),

    -- Kulosaari
    ('HEL-KULOSAARI-001', 'Kulosaari Metro', 60.1795, 25.0125, 0.5, 1014.3, 26),
    ('HEL-KULOSAARI-002', 'Hopeasalmi', 60.1755, 25.0055, 0.7, 1014.1, 28),

    -- Käpylä
    ('HEL-KAPYLA-001', 'Käpylä Station', 60.2105, 24.9495, -1.0, 1015.9, 22),
    ('HEL-KAPYLA-002', 'Koskelantie', 60.2145, 24.9455, -1.3, 1016.2, 20),
    ('HEL-KAPYLA-003', 'Mäkelänkatu Park', 60.2075, 24.9545, -0.8, 1015.6, 24),

    -- Meilahti/Ruskeasuo
    ('HEL-MEILAHTI-001', 'HYKS Main Entrance', 60.1885, 24.8985, 0.2, 1014.9, 25),
    ('HEL-MEILAHTI-002', 'Tukholmankatu', 60.1945, 24.9045, -0.2, 1015.3, 23),
    ('HEL-RUSKEASUO-001', 'Ruskeasuo Station', 60.2005, 24.9145, -0.5, 1015.5, 26),

    -- Hakaniemi/Sörnäinen
    ('HEL-SORNÄINEN-001', 'Sörnäinen Metro', 60.1865, 24.9635, 0.4, 1014.7, 30),
    ('HEL-SORNÄINEN-002', 'Merihaka', 60.1815, 24.9695, 0.6, 1014.4, 32),
    ('HEL-SORNÄINEN-003', 'Mustikkamaa', 60.1765, 24.9945, 0.9, 1013.9, 27),

    -- Arabianranta
    ('HEL-ARABIANRANTA-001', 'Arabia Station', 60.2025, 24.9735, -0.6, 1015.4, 24),
    ('HEL-ARABIANRANTA-002', 'Vanhankaupunginlahti', 60.2085, 24.9865, -0.9, 1015.8, 21),

    -- Malmi
    ('HEL-MALMI-001', 'Malmi Station', 60.2515, 25.0105, -2.1, 1017.2, 18),
    ('HEL-MALMI-002', 'Malmi Airport Area', 60.2545, 25.0285, -2.3, 1017.5, 16),

    -- Oulunkylä
    ('HEL-OULUNKYLA-001', 'Oulunkylä Station', 60.2255, 24.9835, -1.5, 1016.5, 21),
    ('HEL-OULUNKYLA-002', 'Patola', 60.2295, 24.9785, -1.7, 1016.8, 19),

    -- Kumpula/Toukola
    ('HEL-KUMPULA-001', 'Kumpula Campus', 60.2045, 24.9645, -0.7, 1015.6, 23),
    ('HEL-KUMPULA-002', 'Toukola Park', 60.2095, 24.9705, -1.0, 1015.9, 22),

    -- Etu-Töölö (additional density)
    ('HEL-TOOLO-007', 'Temppeliaukio Church', 60.1735, 24.9255, 1.2, 1013.8, 27),
    ('HEL-TOOLO-008', 'Museokatu', 60.1765, 24.9305, 0.9, 1014.1, 26),
    ('HEL-TOOLO-009', 'Runeberg Statue', 60.1755, 24.9355, 1.0, 1013.9, 28),

    -- Kampinmalmi
    ('HEL-KAMPPI-001', 'Ruoholahti Metro', 60.1635, 24.9165, 1.7, 1013.1, 35),
    ('HEL-KAMPPI-002', 'Länsiväylä Bridge', 60.1665, 24.9085, 1.5, 1013.3, 33),
    ('HEL-KAMPPI-003', 'Jätkäsaari East', 60.1565, 24.9215, 2.0, 1012.7, 37),
    ('HEL-KAMPPI-004', 'Hietalahti Market', 60.1615, 24.9285, 1.8, 1013.0, 36),

    -- Additional Central Areas
    ('HEL-CENTER-011', 'National Museum', 60.1755, 24.9315, 0.8, 1014.2, 26),
    ('HEL-CENTER-012', 'Finlandia Hall', 60.1775, 24.9355, 0.6, 1014.4, 25),
    ('HEL-CENTER-013', 'Opera House', 60.1795, 24.9425, 0.4, 1014.6, 24),
    ('HEL-CENTER-014', 'Hakaniemi Hall', 60.1795, 24.9505, 0.5, 1014.5, 26),

    -- Sörnäinen Industrial
    ('HEL-SORNÄINEN-004', 'Kurvi', 60.1895, 24.9685, 0.1, 1015.0, 29),
    ('HEL-SORNÄINEN-005', 'Kääntöpaikka', 60.1925, 24.9735, -0.2, 1015.2, 27),

    -- Pukinmäki
    ('HEL-PUKINMAKI-001', 'Pukinmäki Station', 60.2415, 25.0205, -1.9, 1017.0, 19),
    ('HEL-PUKINMAKI-002', 'Jakomäki Border', 60.2455, 25.0335, -2.2, 1017.3, 17),

    -- Itä-Pasila
    ('HEL-PASILA-005', 'Itä-Pasila', 60.2025, 24.9445, -0.6, 1015.4, 30),
    ('HEL-PASILA-006', 'Messukeskus', 60.2055, 24.9385, -0.8, 1015.6, 28),

    -- Southern Islands/Peninsulas
    ('HEL-ULLANLINNA-001', 'Kaivopuisto Park', 60.1545, 24.9525, 2.5, 1012.2, 34),
    ('HEL-ULLANLINNA-002', 'Tähtitorninmäki', 60.1575, 24.9485, 2.3, 1012.4, 36),
    ('HEL-ULLANLINNA-003', 'Neitsytpolku', 60.1525, 24.9585, 2.6, 1012.0, 32),

    -- Pikku Huopalahti
    ('HEL-HUOPALAHTI-001', 'Huopalahti Station', 60.2185, 24.8865, -1.1, 1016.1, 22),
    ('HEL-HUOPALAHTI-002', 'Etelä-Haaga', 60.2125, 24.8965, -0.9, 1015.8, 24)

on conflict (sensor_code) do nothing;
