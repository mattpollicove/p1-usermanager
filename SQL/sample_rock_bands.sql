-- Sample users for additional rock bands
-- Foo Fighters, Rush, Squeeze, Aerosmith, Led Zeppelin, The Smithereens

INSERT INTO userdata.manyusers (first_name,last_name,username,email,address,work_phone,mobile_phone,company_name,title,department,source,type,user_descr,created_at) VALUES
	 -- Foo Fighters (6 members)
	 ('Dave','Grohl','davegrohl','dave@foofighters.com','Los Angeles, CA, USA','+1-555-8001','+1-555-9001','Foo Fighters','Lead Vocalist / Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Taylor','Hawkins','taylorhawkins','taylor@foofighters.com','Los Angeles, CA, USA','+1-555-8002','+1-555-9002','Foo Fighters','Drummer','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Pat','Smear','patsmear','pat@foofighters.com','Los Angeles, CA, USA','+1-555-8003','+1-555-9003','Foo Fighters','Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Chris','Shiflett','chrisshiflett','chris@foofighters.com','Los Angeles, CA, USA','+1-555-8004','+1-555-9004','Foo Fighters','Lead Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Nate','Mendel','natemendel','nate@foofighters.com','Los Angeles, CA, USA','+1-555-8005','+1-555-9005','Foo Fighters','Bassist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 -- Rush (3 members)
	 ('Rami','Jaffee','ramijaffee','rami@foofighters.com','Los Angeles, CA, USA','+1-555-8006','+1-555-9006','Foo Fighters','Keyboardist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Geddy','Lee','geddylee','geddy@rush.com','Toronto, ON, Canada','+1-555-8101','+1-555-9101','Rush','Lead Vocalist / Bassist / Keyboardist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 -- Squeeze (4 members)
	 ('Alex','Lifeson','alexlifeson','alex@rush.com','Toronto, ON, Canada','+1-555-8102','+1-555-9102','Rush','Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Neil','Peart','neilpeart','neil@rush.com','Toronto, ON, Canada','+1-555-8103','+1-555-9103','Rush','Drummer / Lyricist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Glenn','Tilbrook','glenntilbrook','glenn@squeeze.com','London, UK','+1-555-8201','+1-555-9201','Squeeze','Lead Vocalist / Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 -- Aerosmith (5 members)
	 ('Chris','Difford','chrisdifford','chris@squeeze.com','London, UK','+1-555-8202','+1-555-9202','Squeeze','Guitarist / Vocalist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Jools','Holland','joolsholland','jools@squeeze.com','London, UK','+1-555-8203','+1-555-9203','Squeeze','Keyboardist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Paul','Carrack','paulcarrack','paul@squeeze.com','London, UK','+1-555-8204','+1-555-9204','Squeeze','Keyboardist / Vocalist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Steven','Tyler','styler','steven@aerosmith.com','Boston, MA, USA','+1-555-8301','+1-555-9301','Aerosmith','Lead Vocalist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Joe','Perry','joeperry','joe@aerosmith.com','Boston, MA, USA','+1-555-8302','+1-555-9302','Aerosmith','Lead Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 -- Led Zeppelin (4 members)
	 ('Brad','Whitford','bradwhitford','brad@aerosmith.com','Boston, MA, USA','+1-555-8303','+1-555-9303','Aerosmith','Rhythm Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Tom','Hamilton','tomhamilton','tom@aerosmith.com','Boston, MA, USA','+1-555-8304','+1-555-9304','Aerosmith','Bassist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Joey','Kramer','joeykramer','joey@aerosmith.com','Boston, MA, USA','+1-555-8305','+1-555-9305','Aerosmith','Drummer','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 -- The Smithereens (4 members)
	 ('Robert','Plant','robertplant','robert@ledzeppelin.com','London, UK','+1-555-8401','+1-555-9401','Led Zeppelin','Lead Vocalist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Jimmy','Page','jimmypage','jimmy@ledzeppelin.com','London, UK','+1-555-8402','+1-555-9402','Led Zeppelin','Lead Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('John Paul','Jones','jpjones','johnpaul@ledzeppelin.com','London, UK','+1-555-8403','+1-555-9403','Led Zeppelin','Bassist / Keyboardist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('John','Bonham','johnbonham','john@ledzeppelin.com','London, UK','+1-555-8404','+1-555-9404','Led Zeppelin','Drummer','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Pat','DiNizio','patdinizio','pat@smithereens.com','New Jersey, USA','+1-555-8501','+1-555-9501','The Smithereens','Lead Vocalist / Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Jim','Babjak','jimbabjak','jim@smithereens.com','New Jersey, USA','+1-555-8502','+1-555-9502','The Smithereens','Lead Guitarist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Dennis','Diken','dennisdiken','dennis@smithereens.com','New Jersey, USA','+1-555-8503','+1-555-9503','The Smithereens','Drummer','Performance','Music','Rock',NULL,'2026-04-17 14:08:54'),
	 ('Mike','Mesaros','mikemesaros','mike@smithereens.com','New Jersey, USA','+1-555-8504','+1-555-9504','The Smithereens','Bassist','Performance','Music','Rock',NULL,'2026-04-17 14:08:54');
