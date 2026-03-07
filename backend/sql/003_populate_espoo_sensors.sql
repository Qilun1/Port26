-- Run in Supabase Dashboard -> SQL Editor
-- Populate sensors table with Espoo stations.
-- Data profile: typical March weather with generally higher AQI than Helsinki seed.
-- Placement note: coordinates are intentionally kept away from the Lansivayla highway mainline.

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
    -- Leppavaara / Vermonniitty / Perkkaa (north of highway corridor)
    ('ESP-LEP-001', 'Leppavaara Station North', 60.2215, 24.8135, 1.0, 1012.8, 58),
    ('ESP-LEP-002', 'Sello North Block', 60.2235, 24.8105, 1.2, 1012.6, 62),
    ('ESP-LEP-003', 'Perkkaa East', 60.2205, 24.8225, 0.8, 1012.9, 61),
    ('ESP-LEP-004', 'Perkkaa West', 60.2190, 24.8045, 0.9, 1013.0, 59),
    ('ESP-LEP-005', 'Vermonniitty South', 60.2175, 24.8150, 1.1, 1012.7, 64),
    ('ESP-LEP-006', 'Vermonniitty North', 60.2255, 24.8185, 0.6, 1013.1, 57),
    ('ESP-LEP-007', 'Kilo Ridge', 60.2245, 24.7865, 0.4, 1013.3, 56),
    ('ESP-LEP-008', 'Kilo East', 60.2220, 24.7955, 0.7, 1013.1, 60),
    ('ESP-LEP-009', 'Alberga Park', 60.2265, 24.8080, 0.5, 1013.2, 55),
    ('ESP-LEP-010', 'Lansimaki Leppavaara', 60.2285, 24.8205, 0.3, 1013.4, 54),
    ('ESP-LEP-011', 'Monikko Field', 60.2305, 24.8130, 0.2, 1013.5, 53),
    ('ESP-LEP-012', 'Karakallio South', 60.2330, 24.7995, 0.0, 1013.7, 52),

    -- Tapiola / Otaniemi / Keilaniemi (kept north side or coastal side)
    ('ESP-TAP-001', 'Otaniemi Campus North', 60.1885, 24.8245, 1.4, 1012.3, 63),
    ('ESP-TAP-002', 'Otaniemi Science Park', 60.1915, 24.8330, 1.1, 1012.5, 66),
    ('ESP-TAP-003', 'Aalto Metro North', 60.1868, 24.8275, 1.5, 1012.2, 67),
    ('ESP-TAP-004', 'Keilaniemi Tower North', 60.1828, 24.8288, 1.7, 1012.0, 71),
    ('ESP-TAP-005', 'Keilaniemi Shore South', 60.1605, 24.8335, 2.0, 1011.7, 74),
    ('ESP-TAP-006', 'Tapiola Garden North', 60.1838, 24.8095, 1.3, 1012.4, 65),
    ('ESP-TAP-007', 'Tapiola Cultural Center', 60.1788, 24.8045, 1.6, 1012.1, 69),
    ('ESP-TAP-008', 'Silkkiniitty North', 60.1862, 24.8010, 1.0, 1012.6, 64),
    ('ESP-TAP-009', 'Niittykumpu North', 60.1902, 24.7610, 0.9, 1012.8, 60),
    ('ESP-TAP-010', 'Urheilupuisto North', 60.1888, 24.7795, 1.0, 1012.7, 61),
    ('ESP-TAP-011', 'Hagalund Ridge', 60.1920, 24.8155, 0.7, 1013.0, 58),
    ('ESP-TAP-012', 'Westend Shore', 60.1618, 24.7905, 2.1, 1011.6, 76),
    ('ESP-TAP-013', 'Haukilahti Marina', 60.1568, 24.7718, 2.4, 1011.3, 79),
    ('ESP-TAP-014', 'Mellsten South', 60.1535, 24.7660, 2.6, 1011.1, 81),

    -- Matinkyla / Olari / Friisinmaki (coastal + residential)
    ('ESP-MAT-001', 'Matinkyla South Center', 60.1595, 24.7385, 2.2, 1011.5, 73),
    ('ESP-MAT-002', 'Iso Omena South', 60.1608, 24.7389, 2.3, 1011.4, 75),
    ('ESP-MAT-003', 'Matinkyla Harbor Side', 60.1548, 24.7285, 2.6, 1011.2, 78),
    ('ESP-MAT-004', 'Nuottaniemi Point', 60.1495, 24.7445, 2.8, 1011.0, 82),
    ('ESP-MAT-005', 'Olari North', 60.1765, 24.7315, 1.2, 1012.5, 62),
    ('ESP-MAT-006', 'Olari East', 60.1738, 24.7455, 1.4, 1012.3, 65),
    ('ESP-MAT-007', 'Friisinmaki', 60.1780, 24.7160, 1.1, 1012.6, 61),
    ('ESP-MAT-008', 'Piispanristi South', 60.1640, 24.7305, 2.0, 1011.8, 71),
    ('ESP-MAT-009', 'Soukka North Edge', 60.1662, 24.6805, 1.8, 1012.0, 68),
    ('ESP-MAT-010', 'Soukka Shore', 60.1545, 24.6765, 2.5, 1011.2, 80),
    ('ESP-MAT-011', 'Iivisniemi South', 60.1528, 24.6615, 2.7, 1011.0, 84),
    ('ESP-MAT-012', 'Kaitaa Coastal', 60.1508, 24.7005, 2.6, 1011.1, 83),

    -- Espoonlahti / Kivenlahti / Saunalahti (coastal west)
    ('ESP-LAH-001', 'Espoonlahti South', 60.1478, 24.6525, 2.9, 1010.9, 85),
    ('ESP-LAH-002', 'Lippulaiva South', 60.1492, 24.6540, 2.8, 1011.0, 84),
    ('ESP-LAH-003', 'Kivenlahti Shore East', 60.1520, 24.6415, 2.7, 1011.1, 82),
    ('ESP-LAH-004', 'Kivenlahti Shore West', 60.1532, 24.6320, 2.6, 1011.2, 81),
    ('ESP-LAH-005', 'Saunalahti Bay', 60.1465, 24.6205, 3.0, 1010.8, 88),
    ('ESP-LAH-006', 'Saunaniemi Point', 60.1448, 24.6050, 3.1, 1010.7, 90),
    ('ESP-LAH-007', 'Latokaski South', 60.1635, 24.6455, 1.9, 1011.9, 70),
    ('ESP-LAH-008', 'Nokkalanniemi', 60.1455, 24.6675, 2.8, 1010.9, 86),
    ('ESP-LAH-009', 'Finnoo Coastal', 60.1582, 24.7065, 2.4, 1011.3, 77),
    ('ESP-LAH-010', 'Finnoonsatama South', 60.1568, 24.6995, 2.5, 1011.2, 79),
    ('ESP-LAH-011', 'Kaitalahti South', 60.1485, 24.6895, 2.7, 1011.0, 82),
    ('ESP-LAH-012', 'Hannusjarvi Edge', 60.1705, 24.6685, 1.6, 1012.2, 67),

    -- Espoon keskus / Suvela / Kirstinmaki
    ('ESP-KES-001', 'Espoon Keskus North', 60.2090, 24.6555, 0.8, 1013.0, 59),
    ('ESP-KES-002', 'Kirkkojarvi', 60.2080, 24.6625, 0.9, 1012.9, 60),
    ('ESP-KES-003', 'Suvela East', 60.2055, 24.6455, 1.0, 1012.8, 63),
    ('ESP-KES-004', 'Suvela West', 60.2042, 24.6378, 1.1, 1012.7, 64),
    ('ESP-KES-005', 'Kirstinmaki', 60.2132, 24.6688, 0.6, 1013.2, 57),
    ('ESP-KES-006', 'Tuomarila North', 60.2185, 24.6550, 0.4, 1013.4, 56),
    ('ESP-KES-007', 'Kuurinniitty', 60.2148, 24.6310, 0.7, 1013.1, 58),
    ('ESP-KES-008', 'Nuppulinna Edge', 60.2208, 24.6415, 0.3, 1013.5, 55),
    ('ESP-KES-009', 'Sunan Pelto', 60.2155, 24.6205, 0.5, 1013.3, 54),
    ('ESP-KES-010', 'Muurala North', 60.2240, 24.6565, 0.2, 1013.6, 53),

    -- Kauklahti / Vanttila / Mankki
    ('ESP-KAU-001', 'Kauklahti Station North', 60.1918, 24.5988, 1.2, 1012.4, 66),
    ('ESP-KAU-002', 'Kauklahti Center', 60.1888, 24.6045, 1.3, 1012.3, 67),
    ('ESP-KAU-003', 'Vanttila', 60.1985, 24.5870, 0.9, 1012.7, 62),
    ('ESP-KAU-004', 'Mankki East', 60.1965, 24.6325, 0.8, 1012.8, 61),
    ('ESP-KAU-005', 'Mankki West', 60.1955, 24.6185, 1.0, 1012.6, 63),
    ('ESP-KAU-006', 'Lasilaakso', 60.2025, 24.6030, 0.7, 1013.0, 58),
    ('ESP-KAU-007', 'Kauklahdenkartano', 60.1860, 24.5865, 1.4, 1012.2, 69),
    ('ESP-KAU-008', 'Bastvik North', 60.1795, 24.5605, 1.6, 1012.0, 71),

    -- North Espoo: Kalajarvi / Lakisto / Perusmaki / Niipperi
    ('ESP-NOR-001', 'Kalajarvi Center', 60.3060, 24.6905, -0.8, 1014.2, 49),
    ('ESP-NOR-002', 'Kalajarvi West', 60.3040, 24.6705, -0.9, 1014.3, 48),
    ('ESP-NOR-003', 'Niipperi North', 60.2915, 24.7415, -0.4, 1013.9, 51),
    ('ESP-NOR-004', 'Niipperi South', 60.2855, 24.7355, -0.2, 1013.7, 53),
    ('ESP-NOR-005', 'Perusmaki', 60.2785, 24.7025, 0.1, 1013.5, 55),
    ('ESP-NOR-006', 'Lakisto', 60.2990, 24.7235, -0.6, 1014.0, 50),
    ('ESP-NOR-007', 'Rodberg', 60.2875, 24.6845, -0.1, 1013.6, 54),
    ('ESP-NOR-008', 'Juvanmalmi North', 60.2668, 24.7595, 0.3, 1013.3, 57),
    ('ESP-NOR-009', 'Juvanmalmi East', 60.2645, 24.7725, 0.4, 1013.2, 58),
    ('ESP-NOR-010', 'Karakallio North', 60.2395, 24.7990, 0.0, 1013.6, 56),
    ('ESP-NOR-011', 'Laaksolahti North', 60.2455, 24.7915, -0.1, 1013.7, 55),
    ('ESP-NOR-012', 'Viherlaakso North', 60.2485, 24.8065, -0.2, 1013.8, 54),

    -- Additional coastal and transit-adjacent Espoo (not on Lansivayla)
    ('ESP-COA-001', 'Haukilahdenranta South', 60.1542, 24.7782, 2.5, 1011.1, 80),
    ('ESP-COA-002', 'Westend Beach South', 60.1572, 24.7975, 2.3, 1011.3, 77),
    ('ESP-COA-003', 'Nokkala South', 60.1590, 24.7428, 2.4, 1011.2, 78),
    ('ESP-COA-004', 'Mankkaa North', 60.1965, 24.7685, 0.8, 1012.9, 60),
    ('ESP-COA-005', 'Mankkaa East', 60.1980, 24.7815, 0.7, 1013.0, 59),
    ('ESP-COA-006', 'Niittykumpu East North', 60.1892, 24.7738, 1.0, 1012.7, 61),
    ('ESP-COA-007', 'Urheilupuisto East North', 60.1905, 24.7860, 0.9, 1012.8, 60),
    ('ESP-COA-008', 'Tontunmaki North', 60.1968, 24.8068, 0.6, 1013.1, 58),
    ('ESP-COA-009', 'Bembole North', 60.2340, 24.7455, 0.2, 1013.5, 55),
    ('ESP-COA-010', 'Lippajarvi', 60.2422, 24.7442, -0.1, 1013.8, 53)

on conflict (sensor_code) do nothing;
