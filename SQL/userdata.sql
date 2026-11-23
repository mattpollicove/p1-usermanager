-- Create database
CREATE DATABASE IF NOT EXISTS sampledata;
USE sampledata;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    username VARCHAR(150),
    email VARCHAR(255) UNIQUE,
    address VARCHAR(255),
    work_phone VARCHAR(50),
    mobile_phone VARCHAR(50),
    company_name VARCHAR(150),
    title VARCHAR(150),
    department VARCHAR(150),
    source ENUM('TV','Movie','Music'),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Insert all characters from various franchises (optimized single INSERT)
INSERT IGNORE INTO users
(first_name, last_name, username, email, address, work_phone, mobile_phone, company_name, title, department, source, description)
VALUES
-- Insert Black Panther (MCU) characters
-- Wakanda Royal Family / Core
('TChalla','Udaku', 'tchalla','tchalla@wakanda.gov','Golden City, Wakanda','+1-555-3001','+1-555-4001','Wakanda','King','Leadership','Movie','Last name created for compatibility'),
('Shuri','Udaku', 'shuri','shuri@wakanda.gov','Golden City, Wakanda','+1-555-3002','+1-555-4002','Wakanda','Princess','Science & Technology','Movie','Last name created for compatibility'),
('Ramonda','Udaku', 'ramonda','ramonda@wakanda.gov','Royal Palace, Wakanda','+1-555-3003','+1-555-4003','Wakanda','Queen','Leadership','Movie','Last name created for compatibility'),
-- Dora Milaje
('Okoye','Adisa', 'okoye','okoye@wakanda.gov','Dora Milaje Barracks, Wakanda','+1-555-3004','+1-555-4004','Wakanda','General','Military','Movie','Last name created for compatibility'),
('Ayo','Adisa', 'ayo','ayo@wakanda.gov','Dora Milaje Barracks, Wakanda','+1-555-3005','+1-555-4005','Wakanda','Captain','Military','Movie','Last name created for compatibility'),
-- Wakanda Leadership / Allies
('Wkabi','Jabari', 'wkabi','wkabi@wakanda.gov','Border Tribe Lands, Wakanda','+1-555-3006','+1-555-4006','Wakanda','Commander','Border Security','Movie','Last name created for compatibility'),
('M','Baku','mbaku','mbaku@wakanda.gov','Jabari Mountains, Wakanda','+1-555-3007','+1-555-4007','Wakanda','Leader','Jabari Tribe','Movie'),
('Nakia','Makayi', 'nakia','nakia@wakanda.gov','War Dog Network','+1-555-3008','+1-555-4008','Wakanda','War Dog','Intelligence','Movie','Last name created for compatibility'),
-- Antagonists / External
('Erik','Killmonger','ekillmonger','ekillmonger@wakanda.gov','Unknown','+1-555-3009','+1-555-4009','Wakanda','Usurper','Military','Movie'),
('Ulysses','Klaue','uklaue','uklaue@blackmarket.io','Global','+1-555-3010','+1-555-4010','Black Market','Arms Dealer','Smuggling','Movie'),
-- CIA / US Government
('Everett','Ross','eross','eross@cia.gov','Langley, VA','+1-555-3011','+1-555-4011','CIA','Agent','Intelligence','Movie'),
-- Wakanda Forever additions
('Riri','Williams','rwilliams','rwilliams@mit.edu','Cambridge, MA','+1-555-3012','+1-555-4012','MIT','Student / Engineer','R&D','Movie'),
('Namor','McKenzie', 'namor','namor@talokan.gov','Talokan','+1-555-3013','+1-555-4013','Talokan','King','Leadership','Movie','Last name created for compatibility'),
('Namora','McKenzie', 'namora','namora@talokan.gov','Talokan','+1-555-3014','+1-555-4014','Talokan','Warrior','Military','Movie','Last name created for compatibility'),
('Attuma','Zann', 'attuma','attuma@talokan.gov','Talokan','+1-555-3015','+1-555-4015','Talokan','General','Military','Movie','Last name created for compatibility'),
-- Insert Star Trek characters (core + notable recurring)
-- TOS
('James','Kirk','jkirk','jkirk@starfleet.ufp','1701 Enterprise Way','+1-555-1001','+1-555-2001','Starfleet','Captain','Command','TV',NULL),
('Spock','of Vulcan', 'spock','spock@starfleet.ufp','1701 Enterprise Way','+1-555-1002','+1-555-2002','Starfleet','Commander','Science','TV','Last name created for compatibility'),
('Leonard','McCoy','lmccoy','lmccoy@starfleet.ufp','1701 Enterprise Way','+1-555-1003','+1-555-2003','Starfleet','Chief Medical Officer','Medical','TV'),
('Nyota','Uhura','nuhura','nuhura@starfleet.ufp','1701 Enterprise Way','+1-555-1004','+1-555-2004','Starfleet','Lieutenant','Communications','TV'),
('Hikaru','Sulu','hsulu','hsulu@starfleet.ufp','1701 Enterprise Way','+1-555-1005','+1-555-2005','Starfleet','Lieutenant','Helm','TV'),
('Montgomery','Scott','mscott','mscott@starfleet.ufp','1701 Enterprise Way','+1-555-1006','+1-555-2006','Starfleet','Chief Engineer','Engineering','TV'),
-- TNG
('Jean-Luc','Picard','jpicard','jpicard@starfleet.ufp','Enterprise D HQ','+1-555-1101','+1-555-2101','Starfleet','Captain','Command','TV'),
('William','Riker','wriker','wriker@starfleet.ufp','Enterprise D HQ','+1-555-1102','+1-555-2102','Starfleet','Commander','Command','TV'),
('Data','Soong', 'data','data@starfleet.ufp','Enterprise D HQ','+1-555-1103','+1-555-2103','Starfleet','Lieutenant Commander','Operations','TV','Last name created for compatibility'),
('Geordi','La Forge','glaforge','glaforge@starfleet.ufp','Enterprise D HQ','+1-555-1104','+1-555-2104','Starfleet','Chief Engineer','Engineering','TV'),
('Beverly','Crusher','bcrusher','bcrusher@starfleet.ufp','Enterprise D HQ','+1-555-1105','+1-555-2105','Starfleet','Commander','Medical','TV'),
('Deanna','Troi','dtroi','dtroi@starfleet.ufp','Enterprise D HQ','+1-555-1106','+1-555-2106','Starfleet','Commander','Counseling','TV'),
('Worf','son of Mogh', 'worf','worf@starfleet.ufp','Enterprise D HQ','+1-555-1107','+1-555-2107','Starfleet','Lieutenant','Security','TV','Last name created for compatibility'),
-- DS9
('Benjamin','Sisko','bsisko','bsisko@starfleet.ufp','Deep Space 9','+1-555-1201','+1-555-2201','Starfleet','Commander','Command','TV'),
('Kira','Nerys','knerys','knerys@starfleet.ufp','Deep Space 9','+1-555-1202','+1-555-2202','Starfleet','Major','Operations','TV'),
('Julian','Bashir','jbashir','jbashir@starfleet.ufp','Deep Space 9','+1-555-1203','+1-555-2203','Starfleet','Doctor','Medical','TV'),
('Jadzia','Dax','jdax','jdax@starfleet.ufp','Deep Space 9','+1-555-1204','+1-555-2204','Starfleet','Lieutenant Commander','Science','TV'),
('Miles','OBrien','mobrien','mobrien@starfleet.ufp','Deep Space 9','+1-555-1205','+1-555-2205','Starfleet','Chief','Engineering','TV'),
('Odo','Ital', 'odo','odo@starfleet.ufp','Deep Space 9','+1-555-1206','+1-555-2206','Starfleet','Constable','Security','TV','Last name created for compatibility'),
('Quark','son of Keldar', 'quark','quark@ds9.ufp','Deep Space 9 Promenade','+1-555-1207','+1-555-2207','Quark Enterprises','Owner','Hospitality','TV','Last name created for compatibility'),
-- Voyager
('Kathryn','Janeway','kjaneway','kjaneway@starfleet.ufp','USS Voyager','+1-555-1301','+1-555-2301','Starfleet','Captain','Command','TV'),
('Chakotay','of the Rubber Tree', 'chakotay','chakotay@starfleet.ufp','USS Voyager','+1-555-1302','+1-555-2302','Starfleet','Commander','Command','TV','Last name created for compatibility'),
('Tuvok','of Vulcan', 'tuvok','tuvok@starfleet.ufp','USS Voyager','+1-555-1303','+1-555-2303','Starfleet','Lieutenant Commander','Security','TV','Last name created for compatibility'),
('Tom','Paris','tparis','tparis@starfleet.ufp','USS Voyager','+1-555-1304','+1-555-2304','Starfleet','Lieutenant','Helm','TV'),
('BElanna','Torres','btorres','btorres@starfleet.ufp','USS Voyager','+1-555-1305','+1-555-2305','Starfleet','Chief Engineer','Engineering','TV'),
('Seven','of Nine','seven9','seven9@starfleet.ufp','USS Voyager','+1-555-1306','+1-555-2306','Starfleet','Specialist','Astrometrics','TV'),
('The','Doctor','doctor','doctor@voyager.ufp','USS Voyager','+1-555-1307','+1-555-2307','Starfleet','EMH','Medical','TV'),
-- Enterprise
('Jonathan','Archer','jarcher','jarcher@starfleet.ufp','Enterprise NX-01','+1-555-1401','+1-555-2401','Starfleet','Captain','Command','TV'),
('TPol','of Vulcan', 'tpol','tpol@starfleet.ufp','Enterprise NX-01','+1-555-1402','+1-555-2402','Starfleet','Subcommander','Science','TV','Last name created for compatibility'),
('Charles','Tucker','ctucker','ctucker@starfleet.ufp','Enterprise NX-01','+1-555-1403','+1-555-2403','Starfleet','Commander','Engineering','TV'),
('Malcolm','Reed','mreed','mreed@starfleet.ufp','Enterprise NX-01','+1-555-1404','+1-555-2404','Starfleet','Lieutenant','Tactical/Security','TV'),
('Hoshi','Sato','hsato','hsato@starfleet.ufp','Enterprise NX-01','+1-555-1405','+1-555-2405','Starfleet','Ensign','Communications','TV'),
('Travis','Mayweather','tmayweather','tmayweather@starfleet.ufp','Enterprise NX-01','+1-555-1406','+1-555-2406','Starfleet','Ensign','Helm','TV'),
('Phlox','of Denobula', 'phlox','phlox@starfleet.ufp','Enterprise NX-01','+1-555-1407','+1-555-2407','Starfleet','Doctor','Medical','TV','Last name created for compatibility'),
('Maxwell','Forrest','mforrest','mforrest@starfleet.ufp','Starfleet Command, Earth','+1-555-1408','+1-555-2408','Starfleet','Admiral','Command','TV',NULL),
('Soval','of Vulcan', 'soval','soval@vulcan.ufp','Vulcan High Command','+1-555-1409','+1-555-2409','Vulcan High Command','Ambassador','Diplomacy','TV','Last name created for compatibility'),
('Thylek','Shran','shran','shran@andoria.ufp','Andoria','+1-555-1410','+1-555-2410','Andorian Imperial Guard','Commander','Military','TV'),
-- Discovery
('Michael','Burnham','mburnham','mburnham@starfleet.ufp','USS Discovery','+1-555-1501','+1-555-2501','Starfleet','Commander','Science','TV'),
('Saru','of Kaminar', 'saru','saru@starfleet.ufp','USS Discovery','+1-555-1502','+1-555-2502','Starfleet','Captain','Command','TV','Last name created for compatibility'),
('Paul','Stamets','pstamets','pstamets@starfleet.ufp','USS Discovery','+1-555-1503','+1-555-2503','Starfleet','Commander','Science','TV'),
('Sylvia','Tilly','stilly','stilly@starfleet.ufp','USS Discovery','+1-555-1504','+1-555-2504','Starfleet','Ensign','Engineering','TV'),
('Hugh','Culber','hculber','hculber@starfleet.ufp','USS Discovery','+1-555-1505','+1-555-2505','Starfleet','Lieutenant Commander','Medical','TV'),
('Ash','Tyler','atyler','atyler@starfleet.ufp','USS Discovery','+1-555-1506','+1-555-2506','Starfleet','Lieutenant Commander','Security','TV'),
('Philippa','Georgiou','pgeorgiou','pgeorgiou@starfleet.ufp','USS Shenzhou','+1-555-1507','+1-555-2507','Starfleet','Captain','Command','TV'),
('Gabriel','Lorca','glorca','glorca@starfleet.ufp','USS Discovery','+1-555-1508','+1-555-2508','Starfleet','Captain','Command','TV'),
('Christopher','Pike','cpike','cpike@starfleet.ufp','USS Enterprise','+1-555-1509','+1-555-2509','Starfleet','Captain','Command','TV'),
('Cleveland','Booker','booker','booker@courier.net','Independent Ship','+1-555-1510','+1-555-2510','Independent Courier','Courier','Operations','TV'),
('Adira','Tal','adira','adira@starfleet.ufp','USS Discovery','+1-555-1511','+1-555-2511','Starfleet','Ensign','Science','TV'),
('Katrina','Cornwell','kcornwell','kcornwell@starfleet.ufp','Starfleet Command','+1-555-1512','+1-555-2512','Starfleet','Admiral','Command','TV'),
('Keyla','Detmer','kdetmer','kdetmer@starfleet.ufp','USS Discovery','+1-555-1513','+1-555-2513','Starfleet','Lieutenant','Helm','TV'),
('Joann','Owosekun','jowosekun','jowosekun@starfleet.ufp','USS Discovery','+1-555-1514','+1-555-2514','Starfleet','Lieutenant','Operations','TV'),
-- AC/DC current + core lineup
-- Core band identity (Angus Young)
('Angus','Young','angusyoung','angus@acdc.com','Sydney, Australia','+61-555-4101','+61-555-5101','AC/DC','Lead Guitarist','Performance','Music'),
-- Vocals (current era frontman since classic return)
('Brian','Johnson','brianjohnson','brian@acdc.com','Newcastle, England','+44-555-4102','+44-555-5102','AC/DC','Lead Vocalist','Performance','Music'),
-- Rhythm guitar (Malcolm Young successor role)
('Stevie','Young','stevieyoung','stevie@acdc.com','Sydney, Australia','+61-555-4103','+61-555-5103','AC/DC','Rhythm Guitarist','Performance','Music'),
-- Bass (long-term member, semi-retired but associated with current lineup)
('Cliff','Williams','cliffwilliams','cliff@acdc.com','Florida, USA','+1-555-4104','+1-555-5104','AC/DC','Bassist','Performance','Music'),
-- Drums (classic drummer; intermittent modern touring association)
('Phil','Rudd','philrudd','phil@acdc.com','Tauranga, New Zealand','+64-555-4105','+64-555-5105','AC/DC','Drummer','Performance','Music'),
-- Optional touring/live support (modern era replacement often used)
('Matt','Laug','mattlaug','matt@acdc.com','Las Vegas, USA','+1-555-4106','+1-555-5106','AC/DC','Touring Drummer','Live Performance','Music'),
-- Legacy co-founder reference (retired/deceased but structurally important)
('Malcolm','Young','malcolmyoung','malcolm@acdc.com','Sydney, Australia','+61-555-4107','+61-555-5107','AC/DC','Rhythm Guitarist','Founding Member','Music'),
-- KISS band members (core + legacy representation)
-- Founding / core personas
('Paul','Stanley','paulstanley','paul@kiss.com','New York, USA','+1-555-5201','+1-555-6201','KISS','Rhythm Guitarist / Vocalist','Performance','Music'),
('Gene','Simmons','genesimmons','gene@kiss.com','Los Angeles, USA','+1-555-5202','+1-555-6202','KISS','Bassist / Vocalist','Performance','Music'),
-- Classic lead guitarist
('Ace','Frehley','acefrehley','ace@kiss.com','New York, USA','+1-555-5203','+1-555-6203','KISS','Lead Guitarist','Performance','Music'),
-- Classic drummer
('Peter','Criss','petercriss','peter@kiss.com','New York, USA','+1-555-5204','+1-555-6204','KISS','Drummer','Performance','Music'),
-- Modern era long-term lead guitarist
('Tommy','Thayer','tommythayer','tommy@kiss.com','Oregon, USA','+1-555-5205','+1-555-6205','KISS','Lead Guitarist','Performance','Music'),
-- Modern era drummer (final touring lineup era)
('Eric','Singer','ericsinger','eric@kiss.com','Los Angeles, USA','+1-555-5206','+1-555-6206','KISS','Drummer','Performance','Music'),
-- Star Wars film universe characters (Skywalker saga core + key supporting cast)
-- Jedi / Republic (Prequel + Original era overlap framing)
('Anakin','Skywalker','anakinskywalker','anakin@jedi.order','Tatooine / Coruscant','+1-555-6001','+1-555-7001','Jedi Order','Jedi Knight / Sith Lord','Force Users','Movie',NULL),
('Obi-Wan','Kenobi','obiwankenobi','obiwan@jedi.order','Stewjon / Coruscant','+1-555-6002','+1-555-7002','Jedi Order','Jedi Master','Council','Movie',NULL),
('Qui-Gon','Jinn','quigonjinn','qui-gon@jedi.order','Coruscant','+1-555-6003','+1-555-7003','Jedi Order','Jedi Master','Council','Movie',NULL),
('Yoda','of Dagobah', 'yoda','yoda@jedi.order','Dagobah','+1-555-6004','+1-555-7004','Jedi Order','Grand Master','Council','Movie','Last name created for compatibility'),
('Mace','Windu','macewindu','mace@jedi.order','Coruscant','+1-555-6005','+1-555-7005','Jedi Order','Jedi Master','Council','Movie'),
-- Skywalker lineage / Rebels
('Luke','Skywalker','lukeskywalker','luke@rebellion.org','Tatooine / Ahch-To','+1-555-6006','+1-555-7006','Rebel Alliance','Jedi Master','Leadership','Movie'),
('Leia','Organa','leiaorgana','leia@rebellion.org','Alderaan / Hosnian Prime','+1-555-6007','+1-555-7007','Rebel Alliance','General / Princess','Leadership','Movie'),
('Han','Solo','hansolo','han@smugglers.org','Corellia / Millennium Falcon','+1-555-6008','+1-555-7008','Rebel Alliance','Captain','Smuggling / Command','Movie'),
('Chewbacca','of Kashyyyk', 'chewbacca','chewie@rebellion.org','Kashyyyk','+1-555-6009','+1-555-7009','Rebel Alliance','Co-Pilot','Operations','Movie','Last name created for compatibility'),
('Lando','Calrissian','landocalrissian','lando@cloudcity.org','Bespin','+1-555-6010','+1-555-7010','Rebel Alliance','Administrator / General','Operations','Movie'),
-- Droids
('C-3PO','Protocol Unit', 'c3po','c3po@protocol.droid','Galaxy-wide','+1-555-6011','+1-555-7011','Rebel Alliance','Protocol Droid','Support','Movie','Last name created for compatibility'),
('R2-D2','Astromech Unit', 'r2d2','r2d2@astromech.droid','Galaxy-wide','+1-555-6012','+1-555-7012','Rebel Alliance','Astromech Droid','Engineering','Movie','Last name created for compatibility'),
-- Empire
('Sheev','Palpatine','palpatine','palpatine@empire.gov','Coruscant','+1-555-6013','+1-555-7013','Galactic Empire','Emperor','Leadership','Movie'),
('Darth','Vader','darthvader','vader@empire.gov','Death Star / Executor','+1-555-6014','+1-555-7014','Galactic Empire','Sith Lord','Enforcement','Movie'),
('Grand','Moff Tarkin','tarkin','tarkin@empire.gov','Death Star','+1-555-6015','+1-555-7015','Galactic Empire','Grand Moff','Command','Movie'),
-- Resistance / Sequel era
('Rey','Skywalker', 'rey','rey@resistance.org','Jakku / Ahch-To','+1-555-6016','+1-555-7016','Resistance','Jedi','Force Users','Movie','Last name created for compatibility'),
('Finn','of the Resistance', 'finn','finn@resistance.org','Unknown','+1-555-6017','+1-555-7017','Resistance','Soldier','Infantry','Movie','Last name created for compatibility'),
('Poe','Dameron','poedameron','poe@resistance.org','Yavin / Resistance Fleet','+1-555-6018','+1-555-7018','Resistance','Pilot','Aviation','Movie'),
('Kylo','Ren','kyloren','kylo@firstorder.org','Starkiller Base','+1-555-6019','+1-555-7019','First Order','Supreme Leader','Dark Side','Movie'),
-- Supporting / expanded canon films
('Jyn','Erso','jynerso','jyn@rebellion.org','Jedha','+1-555-6020','+1-555-7020','Rebel Alliance','Operative','Intelligence','Movie'),
('Cassian','Andor','cassianandor','cassian@rebellion.org','Rogue One Cell','+1-555-6021','+1-555-7021','Rebel Alliance','Captain','Intelligence','Movie'),
-- M*A*S*H 4077th personnel
-- Core surgeons
('Benjamin','Pierce','hawkeye','hawkeye@4077.mil','Uijeongbu, South Korea','+1-555-8001','+1-555-9001','4077th MASH','Captain / Surgeon','Surgery','TV'),
('B.J.','Hunnicutt','bjhunnicutt','bj@4077.mil','Uijeongbu, South Korea','+1-555-8002','+1-555-9002','4077th MASH','Captain / Surgeon','Surgery','TV'),
('Trapper','John','trapperjohn','trapper@4077.mil','Uijeongbu, South Korea','+1-555-8003','+1-555-9003','4077th MASH','Captain / Surgeon','Surgery','TV'),
-- Commanding officers
('Sherman','Potter','colonelpotter','potter@4077.mil','Uijeongbu, South Korea','+1-555-8004','+1-555-9004','4077th MASH','Colonel / Commander','Command','TV'),
-- Nursing leadership
('Margaret','Houlihan','hotlips','margaret@4077.mil','Uijeongbu, South Korea','+1-555-8005','+1-555-9005','4077th MASH','Major / Head Nurse','Nursing','TV'),
-- Administrative / support staff
('Walter','OReilly','radar','radar@4077.mil','Uijeongbu, South Korea','+1-555-8006','+1-555-9006','4077th MASH','Corporal / Clerk','Administration','TV'),
('Max','Klinger','klinger','klinger@4077.mil','Uijeongbu, South Korea','+1-555-8007','+1-555-9007','4077th MASH','Corporal / Company Clerk','Administration','TV'),
-- Surgeons / later additions
('Charles','Winchester','winchester','charles@4077.mil','Uijeongbu, South Korea','+1-555-8008','+1-555-9008','4077th MASH','Major / Surgeon','Surgery','TV'),
('Frank','Burns','frankburns','frank@4077.mil','Uijeongbu, South Korea','+1-555-8009','+1-555-9009','4077th MASH','Major / Surgeon','Surgery','TV'),
-- Additional recurring staff
('John','Mulcahy','fathermulcahy','mulcahy@4077.mil','Uijeongbu, South Korea','+1-555-8010','+1-555-9010','4077th MASH','Captain / Chaplain','Medical Support','TV'),
-- Ted Lasso AFC Richmond personnel
-- Coaching staff
('Ted','Lasso','tedlasso','ted@afcrichmond.com','Richmond, London, UK','+44-555-9101','+44-555-0101','AFC Richmond','Head Coach','Coaching Staff','TV'),
('Beard','Willis', 'coachbeard','beard@afcrichmond.com','Richmond, London, UK','+44-555-9102','+44-555-0102','AFC Richmond','Assistant Coach','Coaching Staff','TV'),
('Roy','Kent','roykent','roy@afcrichmond.com','Richmond, London, UK','+44-555-9103','+44-555-0103','AFC Richmond','Assistant Coach','Coaching Staff','TV'),
('Nathan','Shelley','nateshelley','nate@afcrichmond.com','Richmond, London, UK','+44-555-9104','+44-555-0104','AFC Richmond','Kitman / Coach','Coaching Staff','TV'),
-- Ownership / executive staff
('Rebecca','Welton','rebecca','rebecca@afcrichmond.com','Richmond, London, UK','+44-555-9105','+44-555-0105','AFC Richmond','Owner','Executive','TV'),
-- Players (core squad)
('Jamie','Tartt','jamietartt','jamie@afcrichmond.com','Richmond, London, UK','+44-555-9106','+44-555-0106','AFC Richmond','Forward','First Team','TV'),
('Sam','Obisanya','samobisanya','sam@afcrichmond.com','Richmond, London, UK','+44-555-9107','+44-555-0107','AFC Richmond','Defender','First Team','TV'),
('Dani','Rojas','danirojas','dani@afcrichmond.com','Richmond, London, UK','+44-555-9108','+44-555-0108','AFC Richmond','Striker','First Team','TV'),
('Isaac','McAdoo','isaacmcadoo','isaac@afcrichmond.com','Richmond, London, UK','+44-555-9109','+44-555-0109','AFC Richmond','Captain / Defender','First Team','TV'),
('Colin','Hughes','colinhughes','colin@afcrichmond.com','Richmond, London, UK','+44-555-9110','+44-555-0110','AFC Richmond','Winger','First Team','TV'),
('Richard','Montlaur','richardmontlaur','richard@afcrichmond.com','Richmond, London, UK','+44-555-9111','+44-555-0111','AFC Richmond','Midfielder','First Team','TV'),
-- Support / staff
('Trent','Crimm','trentcrimm','trent@afcrichmond.com','London, UK','+44-555-9112','+44-555-0112','AFC Richmond','Journalist / Analyst','Media','TV'),
('Leslie','Higgins','higgins','higgins@afcrichmond.com','Richmond, London, UK','+44-555-9113','+44-555-0113','AFC Richmond','Director of Football','Executive','TV'),
-- Shrinking therapy practice personnel
-- Core therapists
('Jimmy','Laird','jimmylaird','jimmy@westsidecbt.com','Pasadena, CA, USA','+1-555-9201','+1-555-0201','Westside CBT Practice','Psychotherapist','Clinical Staff','TV',NULL),
('Paul','Rhoades','paulrhoades','paul@westsidecbt.com','Pasadena, CA, USA','+1-555-9202','+1-555-0202','Westside CBT Practice','Senior Psychiatrist','Clinical Staff','TV',NULL),
('Gaby','Mendoza', 'gaby','gaby@westsidecbt.com','Pasadena, CA, USA','+1-555-9203','+1-555-0203','Westside CBT Practice','Psychotherapist','Clinical Staff','TV','Last name created for compatibility'),
-- Patients / key narrative participants
('Alice','Laird','alicelaird','alice@client.westsidecbt.com','Pasadena, CA, USA','+1-555-9204','+1-555-0204','Westside CBT Practice','Student / Client','Patients','TV',NULL),
('Sean','Hayes', 'sean','sean@client.westsidecbt.com','Pasadena, CA, USA','+1-555-9205','+1-555-0205','Westside CBT Practice','Client','Patients','TV','Last name created for compatibility'),
-- Support network
('Brian','Walsh', 'brian','brian@westsidecbt.com','Pasadena, CA, USA','+1-555-9206','+1-555-0206','Westside CBT Practice','Attorney / Friend','Support Network','TV','Last name created for compatibility'),
('Liz','Morales', 'liz','liz@westsidecbt.com','Pasadena, CA, USA','+1-555-9207','+1-555-0207','Westside CBT Practice','Neighbor / Manager','Support Network','TV','Last name created for compatibility'),
('Derek','Martinez', 'derek','derek@westsidecbt.com','Pasadena, CA, USA','+1-555-9208','+1-555-0208','Westside CBT Practice','Spouse / Support','Support Network','TV','Last name created for compatibility'),
-- Skeldale House Veterinary Practice (All Creatures Great and Small)
-- Core veterinary surgeons
('James','Herriot','jamesherriot','james@skeldale.vet','Darrowby, Yorkshire, UK','+44-555-9301','+44-555-0301','Skeldale House Veterinary Practice','Veterinary Surgeon','Clinical','TV'),
('Siegfried','Farnon','siegfriedfarnon','siegfried@skeldale.vet','Darrowby, Yorkshire, UK','+44-555-9302','+44-555-0302','Skeldale House Veterinary Practice','Senior Veterinary Surgeon','Clinical Lead','TV'),
('Tristan','Farnon','tristanfarnon','tristan@skeldale.vet','Darrowby, Yorkshire, UK','+44-555-9303','+44-555-0303','Skeldale House Veterinary Practice','Assistant Veterinary Surgeon','Clinical','TV'),
-- Practice management / support
('Mrs','Hall','mrshall','mrs.hall@skeldale.vet','Skeldale House, Yorkshire, UK','+44-555-9304','+44-555-0304','Skeldale House Veterinary Practice','Housekeeper / Practice Manager','Operations','TV'),
-- Key civilian / family relationships
('Helen','Alderson','helena@skeldale.vet','helen.alderson@darrowby.uk','Darrowby, Yorkshire, UK','+44-555-9305','+44-555-0305','Skeldale House Veterinary Practice','Farmer / Veterinary Partner','Community','TV'),
('Diana','Baldwin','dianabaldwin','diana.baldwin@darrowby.uk','Darrowby, Yorkshire, UK','+44-555-9306','+44-555-0306','Skeldale House Veterinary Practice','Farmer / Estate Manager','Community','TV'),
-- Clients / farming community (representative aggregated entries)
('Edwin','Tawson','edwintawson','edwin.tawson@farm.uk','Yorkshire Dales, UK','+44-555-9307','+44-555-0307','Skeldale House Veterinary Practice','Farmer','Clients','TV'),
('Richard','Alderson','richardalderson','richard.alderson@farm.uk','Yorkshire Dales, UK','+44-555-9308','+44-555-0308','Skeldale House Veterinary Practice','Farmer','Clients','TV'),
-- Additional recurring village figures (aggregated roles for schema fit)
('Mrs','Pumphrey','mrspumphrey','pumphrey@darrowby.uk','Darrowby, Yorkshire, UK','+44-555-9309','+44-555-0309','Skeldale House Veterinary Practice','Estate Owner','Clients','TV'),
('Hugh','Hulton','hughhulton','hugh.hulton@darrowby.uk','Darrowby, Yorkshire, UK','+44-555-9310','+44-555-0310','Skeldale House Veterinary Practice','Landowner','Community','TV'),
-- The Big Bang Theory core ecosystem (Caltech + social circle)
-- Core physicists (Caltech)
('Sheldon','Cooper','sheldoncooper','sheldon@caltech.edu','Pasadena, CA, USA','+1-555-9401','+1-555-0401','Caltech','Theoretical Physicist','Physics','TV',NULL),
('Leonard','Hofstadter','leonardhofstadter','leonard@caltech.edu','Pasadena, CA, USA','+1-555-9402','+1-555-0402','Caltech','Experimental Physicist','Physics','TV',NULL),
('Howard','Wolowitz','howardwolowitz','howard@caltech.edu','Pasadena, CA, USA','+1-555-9403','+1-555-0403','Caltech','Aerospace Engineer','Engineering','TV',NULL),
('Raj','Koothrappali','rajk','raj@caltech.edu','Pasadena, CA, USA','+1-555-9404','+1-555-0404','Caltech','Astrophysicist','Astronomy','TV',NULL),
-- Caltech faculty / colleagues
('Leslie','Winkle','lesliewinkle','leslie@caltech.edu','Pasadena, CA, USA','+1-555-9405','+1-555-0405','Caltech','Physicist','Physics','TV',NULL),
('Bert','Kibbler','bertkibbler','bert@caltech.edu','Pasadena, CA, USA','+1-555-9406','+1-555-0406','Caltech','Geologist','Earth Sciences','TV',NULL),
-- University leadership / administration
('Beverly','Hofstadter','beverlyhofstadter','beverly@columbia.edu','New York, NY, USA','+1-555-9407','+1-555-0407','Columbia University','Neuroscientist','Academics','TV',NULL),
-- Friends / partners (social ecosystem)
('Penny','Hofstadter', 'penny','penny@apartment4b.com','Pasadena, CA, USA','+1-555-9408','+1-555-0408','The Cheesecake Factory','Waitress / Sales Rep','Hospitality','TV','Last name created for compatibility'),
('Amy','Farrah Fowler','amyfowler','amy@caltech.edu','Pasadena, CA, USA','+1-555-9409','+1-555-0409','Caltech','Neurobiologist','Neuroscience','TV'),
('Bernadette','Rostenkowski','bernadette','bernadette@pharma.com','Pasadena, CA, USA','+1-555-9410','+1-555-0410','Pharmaceutical Company','Microbiologist','Biotech','TV'),
-- Supporting characters
('Stuart','Bloom','stuartbloom','stuart@comiccenter.com','Pasadena, CA, USA','+1-555-9411','+1-555-0411','Comic Center of Pasadena','Owner','Retail','TV'),
('Mary','Cooper','marycooper','mary@texaschurch.org','Texas, USA','+1-555-9412','+1-555-0412','Church Community','Religious Leader','Community','TV'),
-- The Pitt (Pittsburgh Trauma Medical Center ecosystem)
-- Emergency medicine leadership
('Michael','“Robby” Robinavitch','drrobbie','robbie@ptmc.org','Pittsburgh, PA, USA','+1-555-9501','+1-555-0501','Pittsburgh Trauma Medical Center','Attending Physician','Emergency Medicine','TV'),
-- Emergency department physicians
('Cassie','McKay','cassiemckay','cassie@ptmc.org','Pittsburgh, PA, USA','+1-555-9502','+1-555-0502','PTMC','Emergency Medicine Physician','Emergency Medicine','TV'),
('Jack','Abbot','jackabbot','jack@ptmc.org','Pittsburgh, PA, USA','+1-555-9503','+1-555-0503','PTMC','Resident Physician','Emergency Medicine','TV'),
('Mohammad','“Mo” Khan','mokhan','mo@ptmc.org','Pittsburgh, PA, USA','+1-555-9504','+1-555-0504','PTMC','Resident Physician','Emergency Medicine','TV'),
-- Nursing staff
('Dana','Evans','danaevans','dana@ptmc.org','Pittsburgh, PA, USA','+1-555-9505','+1-555-0505','PTMC','Head Nurse','Emergency Department','TV'),
('Tracy','Martin','tracymartin','tracy@ptmc.org','Pittsburgh, PA, USA','+1-555-9506','+1-555-0506','PTMC','Charge Nurse','Emergency Department','TV'),
-- Hospital administration
('Gloria','Underwood','gloriaunderwood','gloria@ptmc.org','Pittsburgh, PA, USA','+1-555-9507','+1-555-0507','PTMC','Chief Medical Officer','Administration','TV'),
-- Support staff / EMS integration
('Ethan','Collins','ethancollins','ethan@ptmc.org','Pittsburgh, PA, USA','+1-555-9508','+1-555-0508','PTMC','Paramedic','EMS','TV'),
('Riley','Santos','rileysantos','riley@ptmc.org','Pittsburgh, PA, USA','+1-555-9509','+1-555-0509','PTMC','ER Technician','Emergency Department','TV'),
-- Social / patient ecosystem (aggregated roles for schema fit)
('Unknown','Patient01','patient01','patient01@ptmc.org','Pittsburgh, PA, USA','+1-555-9510','+1-555-0510','PTMC','Emergency Patient','Clinical','TV'),
('Unknown','Patient02','patient02','patient02@ptmc.org','Pittsburgh, PA, USA','+1-555-9511','+1-555-0511','PTMC','Emergency Patient','Clinical','TV'),
-- The West Wing (White House administration ecosystem)
-- President and senior leadership
('Josiah','Bartlet','jbartlet','president@whitehouse.gov','1600 Pennsylvania Ave NW, Washington, DC','+1-555-9601','+1-555-0601','The White House','President of the United States','Executive','TV'),
('John','Hoynes','jhoynes','hoynes@whitehouse.gov','Washington, DC','+1-555-9602','+1-555-0602','The White House','Vice President','Executive','TV'),
-- Chief of Staff and senior staff
('Leo','McGarry','leomcgarry','leo@whitehouse.gov','Washington, DC','+1-555-9603','+1-555-0603','The White House','Chief of Staff','Administration','TV'),
('C.J.','Cregg','cjcregg','cj@whitehouse.gov','Washington, DC','+1-555-9604','+1-555-0604','The White House','Press Secretary','Communications','TV'),
('Toby','Ziegler','tobyziegler','toby@whitehouse.gov','Washington, DC','+1-555-9605','+1-555-0605','The White House','Communications Director','Communications','TV'),
('Josh','Lyman','joshlyman','josh@whitehouse.gov','Washington, DC','+1-555-9606','+1-555-0606','The White House','Deputy Chief of Staff','Administration','TV'),
('Sam','Seaborn','samseaborn','sam@whitehouse.gov','Washington, DC','+1-555-9607','+1-555-0607','The White House','Deputy Communications Director','Communications','TV'),
-- Senior advisors / policy staff
('Ainsley','Hayes','ainsleyhayes','ainsley@whitehouse.gov','Washington, DC','+1-555-9608','+1-555-0608','The White House','Associate Counsel','Legal','TV'),
('Will','Bailey','willbailey','will@whitehouse.gov','Washington, DC','+1-555-9609','+1-555-0609','The White House','Speechwriter / Communications','Communications','TV'),
-- Personal staff / operations
('Charlie','Young','charlieyoung','charlie@whitehouse.gov','Washington, DC','+1-555-9610','+1-555-0610','The White House','Personal Aide to President','Operations','TV'),
('Donna','Moss','donnamoss','donna@whitehouse.gov','Washington, DC','+1-555-9611','+1-555-0611','The White House','Senior Assistant','Administration','TV'),
-- Security / military liaison
('Ron','Butterfield','ronbutterfield','ron@whitehouse.gov','Washington, DC','+1-555-9612','+1-555-0612','United States Secret Service','Special Agent in Charge','Security','TV'),
-- Additional senior political figures
('Margaret','Hooper','margarethooper','margaret@whitehouse.gov','Washington, DC','+1-555-9613','+1-555-0613','The White House','Executive Assistant','Administration','TV'),
-- Harry Potter wizarding world ecosystem (Hogwarts + Ministry of Magic)
-- Core Hogwarts students
('Harry','Potter','harrypotter','harry@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9701','+44-555-0701','Hogwarts','Student / Gryffindor','House Gryffindor','Movie'),
('Hermione','Granger','hermionegranger','hermione@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9702','+44-555-0702','Hogwarts','Student / Gryffindor','House Gryffindor','Movie'),
('Ron','Weasley','ronweasley','ron@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9703','+44-555-0703','Hogwarts','Student / Gryffindor','House Gryffindor','Movie'),
-- Hogwarts staff
('Albus','Dumbledore','dumbledore','albus@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9704','+44-555-0704','Hogwarts','Headmaster','Administration','Movie'),
('Minerva','McGonagall','mcgonagall','minerva@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9705','+44-555-0705','Hogwarts','Deputy Headmistress / Professor','Faculty','Movie'),
('Severus','Snape','snape','severus@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9706','+44-555-0706','Hogwarts','Potions Master / Head of Slytherin','Faculty','Movie'),
('Rubeus','Hagrid','hagrid','rubeus@hogwarts.wiz','Hogwarts Grounds','+44-555-9707','+44-555-0707','Hogwarts','Gamekeeper / Care of Magical Creatures','Support Staff','Movie'),
-- Order of the Phoenix / Resistance
('Sirius','Black','siriusblack','sirius@order.wiz','Grimmauld Place','+44-555-9708','+44-555-0708','Order of the Phoenix','Member','Resistance','Movie'),
('Remus','Lupin','remuslupin','remus@order.wiz','United Kingdom','+44-555-9709','+44-555-0709','Order of the Phoenix','Member / Professor','Resistance','Movie'),
('Nymphadora','Tonks','tonks','tonks@order.wiz','United Kingdom','+44-555-9710','+44-555-0710','Order of the Phoenix','Auror','Ministry Enforcement','Movie'),
-- Ministry of Magic
('Cornelius','Fudge','fudge','cornelius@ministry.wiz','Ministry of Magic, London','+44-555-9711','+44-555-0711','Ministry of Magic','Minister for Magic','Government','Movie'),
('Dolores','Umbridge','umbridge','dolores@ministry.wiz','Ministry of Magic, London','+44-555-9712','+44-555-0712','Ministry of Magic','Senior Undersecretary','Administration','Movie'),
-- Death Eaters / antagonists
('Lord','Voldemort','voldemort','tomriddle@dark.wiz','Unknown','+44-555-9713','+44-555-0713','Death Eaters','Dark Lord','Dark Arts','Movie'),
('Bellatrix','Lestrange','bellatrix','bellatrix@dark.wiz','Azkaban / Unknown','+44-555-9714','+44-555-0714','Death Eaters','Lieutenant','Dark Arts','Movie'),
-- Hogwarts students (Slytherin / supporting)
('Draco','Malfoy','dracomalfoy','draco@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9715','+44-555-0715','Hogwarts','Student / Slytherin','House Slytherin','Movie'),
-- Supporting wizarding world
('Neville','Longbottom','nevillelongbottom','neville@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9716','+44-555-0716','Hogwarts','Student / Gryffindor','House Gryffindor','Movie'),
('Luna','Lovegood','lunalovegood','luna@hogwarts.wiz','Hogwarts School of Witchcraft and Wizardry','+44-555-9717','+44-555-0717','The Quibbler','Student / Ravenclaw','House Ravenclaw','Movie'),
-- MCU Avengers universe (core Avengers + major allied/antagonist systems)
-- Core Avengers (founding + key members)
('Steve','Rogers','steverogers','steve@avengers.org','Brooklyn, NY, USA','+1-555-9802','+1-555-0802','Avengers','Captain America','Leadership','Movie',NULL),
('Bruce','Banner','brucebanner','bruce@avengers.org','Various','+1-555-9804','+1-555-0804','Avengers','Hulk / Scientist','Science','Movie',NULL),
('Natasha','Romanoff','natasharomanoff','natasha@shield.gov','Unknown','+1-555-9805','+1-555-0805','S.H.I.E.L.D.','Agent','Espionage','Movie',NULL),
('Clint','Barton','clintbarton','clint@shield.gov','Unknown','+1-555-9806','+1-555-0806','S.H.I.E.L.D.','Hawkeye / Agent','Operations','Movie',NULL),
-- S.H.I.E.L.D. leadership / intelligence
('Nick','Fury','nickfury','fury@shield.gov','Unknown','+1-555-9807','+1-555-0807','S.H.I.E.L.D.','Director','Intelligence','Movie',NULL),
('Phil','Coulson','philcoulson','coulson@shield.gov','Unknown','+1-555-9808','+1-555-0808','S.H.I.E.L.D.','Agent','Field Operations','Movie',NULL),
-- Avengers leadership expansion
('Wanda','Maximoff','wandamaximoff','wanda@avengers.org','Sokovia / New York','+1-555-9809','+1-555-0809','Avengers','Scarlet Witch','Reality Manipulation','Movie',NULL),
('Vision','Ultron', 'vision','vision@avengers.org','Avengers Compound','+1-555-9810','+1-555-0810','Avengers','Android / Strategist','Artificial Intelligence','Movie','Last name created for compatibility'),
('Pietro','Maximoff','pietromaximoff','pietro@avengers.org','Sokovia','+1-555-9811','+1-555-0811','Avengers','Quicksilver','Enhanced Abilities','Movie',NULL),
-- Antagonists
('Thanos','of Titan','thanos','thanos@blackorder.cosmos','Titan','+1-555-9820','+1-555-0820','Black Order','Warlord','Genocide Strategy','Movie','Last name created for compatibility'),
-- MCU Thunderbolts roster (government-aligned covert operations team)
-- Core Thunderbolts team members
('Yelena','Belova','yelenabelova','yelena@cia.gov','Unknown','+1-555-9901','+1-555-0901','CIA / U.S. Government','Black Widow Operative','Covert Operations','Movie'),
('Bucky','Barnes','buckybarnes','bucky@cia.gov','Unknown','+1-555-9902','+1-555-0902','U.S. Government','Winter Soldier / Operative','Covert Operations','Movie'),
('John','Walker','johnwalker','walker@dod.gov','United States','+1-555-9903','+1-555-0903','U.S. Government','U.S. Agent','Special Operations','Movie'),
('Ava','Starr','ghost','ghost@aimtech.org','Unknown','+1-555-9904','+1-555-0904','A.I.M. / Government Program','Ghost','Experimental Operations','Movie'),
('Antonia','Dreykov','taskmaster','taskmaster@redroom.org','Unknown','+1-555-9905','+1-555-0905','Red Room','Taskmaster','Assassination Training','Movie'),
-- Government oversight / command structure
('Valentina','de Fontaine','valentina@cia.gov','val@cia.gov','Washington, DC, USA','+1-555-9906','+1-555-0906','CIA','Director of Intelligence','Leadership','Movie'),
-- Supporting operatives / intelligence ecosystem
('Red','Guardian','alexei','alexei@cia.gov','Russia','+1-555-9907','+1-555-0907','Former Soviet Program','Enhanced Operative','Covert Ops','Movie'),
('James','Barnes','winterbarnes','james@cia.gov','Unknown','+1-555-9908','+1-555-0908','U.S. Government','Winter Soldier (Recovered Operative)','Rehabilitation / Ops','Movie'),
-- Engineering / logistics support (Thunderbolts-adjacent infrastructure)
('Melina','Vostokoff','melina@redroom.org','melina@redroom.org','Unknown','+1-555-9909','+1-555-0909','Red Room','Scientist / Operative','R&D','Movie'),
-- MCU Fantastic Four roster (Baxter Foundation / FF team)
-- Core Fantastic Four team
('Reed','Richards','reedrichards','reed@baxterfoundation.org','New York, NY, USA','+1-555-9911','+1-555-0911','Baxter Foundation','Mister Fantastic','Scientific Research','Movie',NULL),
('Sue','Storm','suestorm','sue@baxterfoundation.org','New York, NY, USA','+1-555-9912','+1-555-0912','Baxter Foundation','Invisible Woman','Scientific Research','Movie',NULL),
('Johnny','Storm','johnnystorm','johnny@baxterfoundation.org','New York, NY, USA','+1-555-9913','+1-555-0913','Baxter Foundation','Human Torch','Experimental Physics','Movie',NULL),
('Ben','Grimm','bengrimm','ben@baxterfoundation.org','New York, NY, USA','+1-555-9914','+1-555-0914','Baxter Foundation','The Thing','Engineering / Operations','Movie',NULL),
-- Institutional leadership / funding
('Alicia','Masters','aliciamasters','alicia@baxterfoundation.org','New York, NY, USA','+1-555-9915','+1-555-0915','Baxter Foundation','Artist / Civilian Partner','Public Relations','Movie',NULL),
('Nathaniel','Richards','nathanielrichards','nathaniel@baxterfoundation.org','Multiverse / Unknown','+1-555-9916','+1-555-0916','Baxter Foundation','Scientist / Temporal Researcher','Advanced Physics','Movie',NULL),
-- Government / external oversight
('A.I.','Monitoring Unit','aimonitor','ai@shield.gov','United States','+1-555-9917','+1-555-0917','S.H.I.E.L.D.','Scientific Oversight System','Meta-Science','Movie',NULL),
-- Antagonistic forces (cosmic / interdimensional)
('Victor','Von Doom','doom','doom@latveria.gov','Latveria','+1-555-9918','+1-555-0918','Latveria','Doctor Doom','State Leadership / Science','Movie',NULL),
-- Cosmic entities (simplified representation)
('Galactus','the Devourer', 'galactus','galactus@cosmic.entity','Deep Space','+1-555-9919','+1-555-0919','Cosmic Entity','World Devourer','Cosmic Forces','Movie','Last name created for compatibility'),
('Shalla','Bal','shallabal','shalla@cosmic.entity','Silver Surfer Fleet','+1-555-9920','+1-555-0920','Cosmic Entity','Herald','Cosmic Forces','Movie',NULL),
-- MCU Spider-Man ecosystem (Stark-linked street-level operations)
-- Core Spider-Man identity
('Peter','Parker','peterparker','peter@midtown.edu','Queens, NY, USA','+1-555-9921','+1-555-0921','Midtown School of Science & Tech','Spider-Man / Student','Street-Level Hero','Movie'),
-- Immediate allies / household
('May','Parker','mayparker','may@midtown.edu','Queens, NY, USA','+1-555-9922','+1-555-0922','Midtown School of Science & Tech','Guardian / Support','Civilian Support','Movie'),
-- Friends / classmates
('Ned','Leeds','nedleeds','ned@midtown.edu','Queens, NY, USA','+1-555-9923','+1-555-0923','Midtown School of Science & Tech','Best Friend / Operator','Support Network','Movie'),
('Michelle','Jones','mjones','mj@midtown.edu','Queens, NY, USA','+1-555-9924','+1-555-0924','Midtown School of Science & Tech','Student / Analyst','Support Network','Movie'),
-- Antagonists (street + multiversal)
('Adrian','Toomes','vulture','adrian@damagecontrol.gov','New York, NY, USA','+1-555-9927','+1-555-0927','Damage Control','Vulture','Black Market Tech','Movie'),
('Quentin','Beck','mysterio','quentin@starkindustries.com','Unknown','+1-555-9928','+1-555-0928','Stark Industries (Former Contractor)','Mysterio','Illusion Tech','Movie'),
-- Multiversal / advanced threats
('Max','Dillon','electro','max@oscorp.com','New York, NY, USA','+1-555-9929','+1-555-0929','Oscorp','Electro','Energy Systems','Movie'),
('Norman','Osborn','green_goblin','norman@oscorp.com','New York, NY, USA','+1-555-9930','+1-555-0930','Oscorp','Green Goblin','Corporate / Experimental Tech','Movie'),
-- Additional Spider-Man allies (multiverse support)
('Doctor','Strange','strangespider','strange@kamar-taj.org','New York / Kamar-Taj','+1-555-9931','+1-555-0931','Kamar-Taj','Sorcerer Supreme','Mystic Arts','Movie'),
-- MCU Guardians of the Galaxy cosmic ecosystem
-- Core Guardians team
('Peter','Quill','starlord','peter@guardians.space','Earth / Milano','+1-555-9941','+1-555-0941','Guardians of the Galaxy','Captain / Star-Lord','Leadership / Operations','Movie',NULL),
('Gamora','Zen Whoberi', 'gamora','gamora@guardians.space','Zen-Whoberi / Space','+1-555-9942','+1-555-0942','Guardians of the Galaxy','Assassin / Warrior','Combat','Movie','Last name created for compatibility'),
('Drax','the Destroyer','drax','drax@guardians.space','Space','+1-555-9943','+1-555-0943','Guardians of the Galaxy','Warrior','Combat','Movie',NULL),
('Rocket','Raccoon','rocket','rocket@guardians.space','Space','+1-555-9944','+1-555-0944','Guardians of the Galaxy','Tactical Specialist','Engineering / Weapons','Movie',NULL),
('Groot','Flora Colossus', 'groot','groot@guardians.space','Space','+1-555-9945','+1-555-0945','Guardians of the Galaxy','Enforcer','Support','Movie','Last name created for compatibility'),
('Nebula','Luphomoid', 'nebula','nebula@guardians.space','Titan / Space','+1-555-9946','+1-555-0946','Guardians of the Galaxy','Assassin / Operative','Intelligence','Movie','Last name created for compatibility'),
-- Extended Guardians (later roster expansion)
('Mantis','Celestial', 'mantis','mantis@guardians.space','Knowhere','+1-555-9947','+1-555-0947','Guardians of the Galaxy','Empath','Support / Psychic','Movie','Last name created for compatibility'),
-- Ravagers faction
('Yondu','Udonta','yondu','yondu@ravagers.space','Space','+1-555-9948','+1-555-0948','Ravagers','Captain','Piracy / Operations','Movie',NULL),
('Krugarr','Obfonteri', 'kraglin','kraglin@ravagers.space','Space','+1-555-9949','+1-555-0949','Ravagers','Lieutenant','Operations','Movie','Last name created for compatibility'),
-- Nova Corps / Xandar governance
('Irani','Raeel','novaprime','novaprime@xandar.gov','Xandar','+1-555-9950','+1-555-0950','Nova Corps','Nova Prime','Government / Security','Movie'),
-- Antagonists
('Ronan','the Accuser','ronan','ronan@kree.empire','Kree Empire','+1-555-9951','+1-555-0951','Kree Empire','Accuser','Military / Enforcement','Movie'),
('Ego','the Living Planet','ego','ego@celestial.space','Cosmic Space','+1-555-9952','+1-555-0952','Celestial Entity','Cosmic Being','Cosmic','Movie'),
-- Corporate / galactic economy layer
('The','Collector','collector','collector@knowhere.space','Knowhere','+1-555-9953','+1-555-0953','Independent Collectorate','Artifact Broker','Black Market','Movie'),
-- MCU Agents of S.H.I.E.L.D. ecosystem (S.H.I.E.L.D. + HYDRA + Inhumans + allied assets)
-- Core S.H.I.E.L.D. team
('Melinda','May','melindamay','may@shield.gov','United States','+1-555-9962','+1-555-0962','S.H.I.E.L.D.','Agent','Field Operations','TV',NULL),
('Daisy','Johnson','quake','daisy@shield.gov','United States','+1-555-9963','+1-555-0963','S.H.I.E.L.D.','Inhuman / Agent','Enhanced Operations','TV',NULL),
('Leo','Fitz','fitz','fitz@shield.gov','United States','+1-555-9964','+1-555-0964','S.H.I.E.L.D.','Engineer','R&D','TV',NULL),
('Jemma','Simmons','simmons','jemma@shield.gov','United States','+1-555-9965','+1-555-0965','S.H.I.E.L.D.','Biochemist','R&D','TV',NULL),
-- Strategic leadership / command structure
('Alphonso','Mackenzie','mack','mack@shield.gov','United States','+1-555-9966','+1-555-0966','S.H.I.E.L.D.','Director / Mechanic','Operations','TV',NULL),
-- HYDRA infiltration layer
('Grant','Ward','grantward','ward@hydra.org','Unknown','+1-555-9967','+1-555-0967','HYDRA','Agent','Covert Operations','TV',NULL),
('John','Garrett','garrett','garrett@hydra.org','Unknown','+1-555-9968','+1-555-0968','HYDRA','Cybernetic Operative','Leadership','TV',NULL),
-- Inhuman leadership / Kree influence
('Jiaying','Chen', 'jiaying','jiaying@afterlife.org','Afterlife','+1-555-9969','+1-555-0969','Inhumans','Leader','Enhanced Population','TV','Last name created for compatibility'),
('Lincoln','Campbell','lincoln','lincoln@afterlife.org','Afterlife','+1-555-9970','+1-555-0970','Inhumans','Inhuman','Enhanced Operations','TV',NULL),
-- Antagonist organizations
('Holden','Radcliffe','radcliffe','radcliffe@ai.dev','Unknown','+1-555-9972','+1-555-0972','A.I. Research Division','Scientist','Artificial Intelligence','TV',NULL),
('AIDA','Framework', 'aida','aida@ai.dev','Digital Construct','+1-555-9973','+1-555-0973','Artificial Intelligence','Advanced AI','Systems Intelligence','TV','Last name created for compatibility'),
-- External intelligence / allies
('Robert','Gonzales','gonzales','gonzales@shield.gov','United States','+1-555-9974','+1-555-0974','S.H.I.E.L.D.','Director','Leadership','TV'),
-- X-Men / Fox Marvel Mutant ecosystem (Xavier Institute + Brotherhood + Weapon X)
-- Xavier Institute (X-Men core team)
('Charles','Xavier','professorx','charles@xavierinstitute.edu','Westchester, NY, USA','+1-555-9701','+1-555-0701','Xavier Institute','Founder / Telepath','Leadership','Movie'),
('Logan','Howlett','wolverine','logan@xavierinstitute.edu','North America','+1-555-9702','+1-555-0702','Xavier Institute','Mutant Operative','Combat','Movie'),
('Ororo','Munroe','storm','ororo@xavierinstitute.edu','Global','+1-555-9703','+1-555-0703','Xavier Institute','Weather Manipulator','Field Operations','Movie'),
('Scott','Summers','cyclops','scott@xavierinstitute.edu','Westchester, NY, USA','+1-555-9704','+1-555-0704','Xavier Institute','Field Leader','Leadership','Movie'),
('Jean','Grey','jeangrey','jean@xavierinstitute.edu','Westchester, NY, USA','+1-555-9705','+1-555-0705','Xavier Institute','Telepath / Telekinetic','Science / Mutant Research','Movie'),
('Kurt','Wagner','nightcrawler','kurt@xavierinstitute.edu','Germany / USA','+1-555-9706','+1-555-0706','Xavier Institute','Teleportation Specialist','Field Operations','Movie'),
('Raven','Darkhölme','mystique','raven@brotherhood.org','Global','+1-555-9707','+1-555-0707','Brotherhood of Mutants','Shapeshifter / Operative','Covert Ops','Movie'),
-- Brotherhood of Mutants
('Erik','Lehnsherr','magneto','erik@brotherhood.org','Global','+1-555-9708','+1-555-0708','Brotherhood of Mutants','Magnetism Controller','Leadership','Movie'),
-- Xavier support / administration
('Hank','McCoy','beast','hank@xavierinstitute.edu','Westchester, NY, USA','+1-555-9709','+1-555-0709','Xavier Institute','Scientist / Mutant','R&D','Movie'),
('Kitty','Pryde','shadowcat','kitty@xavierinstitute.edu','Westchester, NY, USA','+1-555-9710','+1-555-0710','Xavier Institute','Phasing Specialist','Field Operations','Movie'),
-- Weapon X / Government programs
('William','Stryker','stryker','william@weaponx.gov','Unknown','+1-555-9711','+1-555-0711','Weapon X Program','Program Director','Military Science','Movie'),
('Victor','Creed','sabertooth','victor@weaponx.gov','Unknown','+1-555-9712','+1-555-0712','Weapon X Program','Enhanced Operative','Combat','Movie'),
-- Independent / future timelines
('Peter','Maximoff','quicksilver','peter@xavierinstitute.edu','Global','+1-555-9713','+1-555-0713','Xavier Institute','Speedster','Field Operations','Movie'),
-- Sentinels / AI antagonist systems
('Nimrod','System','nimrod','nimrod@sentinel.ai','Automated Systems','+1-555-9714','+1-555-0714','Sentinel Program','Autonomous AI','Mutant Containment','Movie'),
-- DC cinematic universe ecosystem (Justice League + allied and antagonist factions)
-- Core Justice League members
('Clark','Kent','superman','clark@dailyplanet.com','Metropolis, USA','+1-555-1001','+1-555-2001','Justice League','Superman','Leadership / Heroics','Movie',NULL),
('Bruce','Wayne','batman','bruce@wayneenterprises.com','Gotham City, USA','+1-555-1002','+1-555-2002','Wayne Enterprises','Batman','Strategy / Operations','Movie',NULL),
('Diana','Prince','wonderwoman','diana@themyscira.org','Themyscira','+1-555-1003','+1-555-2003','Justice League','Wonder Woman','Combat / Diplomacy','Movie',NULL),
('Barry','Allen','flash','barry@ccpd.gov','Central City, USA','+1-555-1004','+1-555-2004','Justice League','The Flash','Science / Speed Force','Movie',NULL),
('Arthur','Curry','aquaman','arthur@atlantis.gov','Atlantis','+1-555-1005','+1-555-2005','Atlantis','King of Atlantis','Marine Leadership','Movie',NULL),
('Victor','Stone','cyborg','victor@justiceleague.org','Detroit, USA','+1-555-1006','+1-555-2006','Justice League','Cyborg','Technology / Systems','Movie',NULL),
-- Gotham ecosystem
('Selina','Kyle','catwoman','selina@gotham.net','Gotham City, USA','+1-555-1007','+1-555-2007','Independent','Catwoman','Operations / Infiltration','Movie',NULL),
('Alfred','Pennyworth','alfred','alfred@wayneenterprises.com','Gotham City, USA','+1-555-1008','+1-555-2008','Wayne Enterprises','Chief Steward / Advisor','Operations','Movie',NULL),
-- Kryptonian lineage / science
('Jor','El','jor_el','jor@krypton.science','Krypton','+1-555-1009','+1-555-2009','Krypton Science Council','Scientist','Science / Leadership','Movie',NULL),
('Lois','Lane','loislane','lois@dailyplanet.com','Metropolis, USA','+1-555-1010','+1-555-2010','Daily Planet','Investigative Journalist','Media','Movie',NULL),
-- Amazon / Atlantean support
('Mera','Y''Mera', 'mera','mera@atlantis.gov','Atlantis','+1-555-1011','+1-555-2011','Atlantis','Queen / Diplomat','Royalty / Diplomacy','Movie','Last name created for compatibility'),
-- Antagonist forces
('Diana','Prince (Ares Conflict)','ares','ares@mythrealm','Mythological Realm','+1-555-1012','+1-555-2012','Olympian Forces','God of War','Cosmic / Mythic','Movie',NULL),
('Steppenwolf','of Apokolips', 'steppenwolf','steppenwolf@apokolips.dark','Apokolips','+1-555-1013','+1-555-2013','Apokolips','Invasion Commander','Military','Movie','Last name created for compatibility'),
('Darkseid','of Apokolips', 'darkseid','darkseid@apokolips.dark','Apokolips','+1-555-1014','+1-555-2014','Apokolips','Ruler','Cosmic Domination','Movie','Last name created for compatibility'),
-- Metahuman / speed force ecosystem
('Jai','Allen','kidflash','jai@ccpd.gov','Central City, USA','+1-555-1015','+1-555-2015','Justice League','Speedster','Field Operations','Movie',NULL),
-- Scientific / tech support
('Silas','Stone','silasstone','silas@star-labs.org','Detroit, USA','+1-555-1016','+1-555-2016','S.T.A.R. Labs','Scientist','R&D','Movie',NULL),
-- Grateful Dead ecosystem (core members + long-term touring collective)
-- Core founding members
('Jerry','Garcia','jerrygarcia','jerry@gratefuldead.com','San Francisco, CA, USA','+1-555-1101','+1-555-2101','Grateful Dead','Lead Guitarist / Vocalist','Performance','Music'),
('Bob','Weir','bobweir','bob@gratefuldead.com','San Francisco, CA, USA','+1-555-1102','+1-555-2102','Grateful Dead','Rhythm Guitarist / Vocalist','Performance','Music'),
('Phil','Lesh','phillesh','phil@gratefuldead.com','San Francisco, CA, USA','+1-555-1103','+1-555-2103','Grateful Dead','Bassist','Performance','Music'),
('Bill','Kreutzmann','billkreutzmann','bill@gratefuldead.com','San Francisco, CA, USA','+1-555-1104','+1-555-2104','Grateful Dead','Drummer','Performance','Music'),
-- Key percussion expansion
('Mickey','Hart','mickeyhart','mickey@gratefuldead.com','San Francisco, CA, USA','+1-555-1105','+1-555-2105','Grateful Dead','Drummer / Percussion','Rhythm Section','Music'),
-- Keyboard evolution (representative key eras)
('Ron','McKernan','pigpen','pigpen@gratefuldead.com','San Francisco, CA, USA','+1-555-1106','+1-555-2106','Grateful Dead','Keyboardist / Vocalist','Founding Member','Music'),
('Keith','Godchaux','keithgodchaux','keith@gratefuldead.com','San Francisco, CA, USA','+1-555-1107','+1-555-2107','Grateful Dead','Keyboardist','Performance','Music'),
('Brent','Mydland','brentmydland','brent@gratefuldead.com','San Francisco, CA, USA','+1-555-1108','+1-555-2108','Grateful Dead','Keyboardist / Vocalist','Performance','Music'),
('Vince','Welnick','vincewelnick','vince@gratefuldead.com','San Francisco, CA, USA','+1-555-1109','+1-555-2109','Grateful Dead','Keyboardist','Performance','Music'),
-- Later era touring collective
('John','Mayer','johnmayer','john@deadandco.com','USA','+1-555-1110','+1-555-2110','Dead & Company','Lead Guitarist','Touring Ensemble','Music'),
-- Support / extended family ecosystem (Deadhead touring infrastructure)
('Sam','Cutler','samcutler','sam@gratefuldead.com','USA','+1-555-1111','+1-555-2111','Grateful Dead','Tour Manager','Operations','Music'),
-- Queen ecosystem (core band + touring structure)
('Freddie','Mercury','freddiemercury','freddie@queen.com','London, UK','+44-555-1201','+44-555-2201','Queen','Lead Vocalist','Performance','Music'),
('Brian','May','brianmay','brian@queen.com','London, UK','+44-555-1202','+44-555-2202','Queen','Lead Guitarist','Performance','Music'),
('Roger','Taylor','rogertaylor','roger@queen.com','London, UK','+44-555-1203','+44-555-2203','Queen','Drummer','Rhythm Section','Music'),
('John','Deacon','johndeacon','john@queen.com','London, UK','+44-555-1204','+44-555-2204','Queen','Bassist','Performance','Music'),
-- The Beatles ecosystem (core band)
('John','Lennon','johnlennon','john@beatles.com','Liverpool, UK','+44-555-1301','+44-555-2301','The Beatles','Co-Lead Vocalist / Rhythm Guitar','Performance','Music'),
('Paul','McCartney','paulmccartney','paul@beatles.com','Liverpool, UK','+44-555-1302','+44-555-2302','The Beatles','Co-Lead Vocalist / Bassist','Performance','Music'),
('George','Harrison','georgeharrison','george@beatles.com','Liverpool, UK','+44-555-1303','+44-555-2303','The Beatles','Lead Guitarist','Performance','Music'),
('Ringo','Starr','ringostarr','ringo@beatles.com','Liverpool, UK','+44-555-1304','+44-555-2304','The Beatles','Drummer','Rhythm Section','Music'),
-- The Rolling Stones ecosystem (core band + touring structure)
('Mick','Jagger','mickjagger','mick@rollingstones.com','London, UK','+44-555-1401','+44-555-2401','The Rolling Stones','Lead Vocalist','Performance','Music'),
('Keith','Richards','keithrichards','keith@rollingstones.com','London, UK','+44-555-1402','+44-555-2402','The Rolling Stones','Guitarist','Performance','Music'),
('Charlie','Watts','charliewatts','charlie@rollingstones.com','London, UK','+44-555-1403','+44-555-2403','The Rolling Stones','Drummer','Rhythm Section','Music'),
('Ronnie','Wood','ronniewood','ronnie@rollingstones.com','London, UK','+44-555-1404','+44-555-2404','The Rolling Stones','Guitarist','Performance','Music'),
('Jimmy','Buffett','jimmybuffett','jimmy@coralreefer.com','Key West, FL, USA','+1-555-1501','+1-555-2501','Jimmy Buffett & Coral Reefer Band','Lead Vocalist / Guitar','Performance','Music'),
-- Coral Reefer Band (representative core touring members)
('Mac','McAnally','macmcanally','mac@coralreefer.com','USA','+1-555-1502','+1-555-2502','Coral Reefer Band','Guitarist / Vocalist','Performance','Music'),
('Robert','Greenidge','robertgreenidge','robert@coralreefer.com','Trinidad & Tobago','+1-555-1503','+1-555-2503','Coral Reefer Band','Steel Drummer','Rhythm Section','Music'),
('Peter','Mayer','petermayer','peter@coralreefer.com','USA','+1-555-1504','+1-555-2504','Coral Reefer Band','Guitarist','Performance','Music'),
('Rufus','Thibodeaux','rufusthibodeaux','rufus@coralreefer.com','USA','+1-555-1505','+1-555-2505','Coral Reefer Band','Fiddler / Instrumentalist','Performance','Music'),
('Robbie','Robertson','robbierobertson','robbie@theband.com','Canada','+1-555-1601','+1-555-2601','The Band','Guitarist / Songwriter','Performance','Music'),
('Levon','Helm','levonhelm','levon@theband.com','USA','+1-555-1602','+1-555-2602','The Band','Drummer / Vocalist','Performance','Music'),
('Rick','Danko','rickdanko','rick@theband.com','Canada','+1-555-1603','+1-555-2603','The Band','Bassist / Vocalist','Performance','Music'),
('Richard','Manuel','richardmanuel','richard@theband.com','Canada','+1-555-1604','+1-555-2604','The Band','Keyboardist / Vocalist','Performance','Music'),
('Garth','Hudson','garthhudson','garth@theband.com','Canada','+1-555-1605','+1-555-2605','The Band','Multi-instrumentalist','Performance','Music'),
('Bruce','Springsteen','brucespringsteen','bruce@estreetband.com','New Jersey, USA','+1-555-1701','+1-555-2701','Bruce Springsteen & E Street Band','Lead Vocalist / Guitar','Performance','Music'),
-- E Street Band core members
('Steven','Van Zandt','stevenvanzandt','steve@estreetband.com','New Jersey, USA','+1-555-1702','+1-555-2702','E Street Band','Guitarist / Vocalist','Performance','Music'),
('Max','Weinberg','maxweinberg','max@estreetband.com','New Jersey, USA','+1-555-1703','+1-555-2703','E Street Band','Drummer','Rhythm Section','Music'),
('Garry','Tallent','garrytallent','garry@estreetband.com','New Jersey, USA','+1-555-1704','+1-555-2704','E Street Band','Bassist','Rhythm Section','Music'),
('Roy','Bittan','roybittan','roy@estreetband.com','New Jersey, USA','+1-555-1705','+1-555-2705','E Street Band','Pianist','Performance','Music'),
('Clarence','Clemons','clarenceclemons','clarence@estreetband.com','USA','+1-555-1706','+1-555-2706','E Street Band','Saxophonist','Performance','Music'),
('Nils','Lofgren','nilslofgren','nils@estreetband.com','USA','+1-555-1707','+1-555-2707','E Street Band','Guitarist','Performance','Music'),
('Huey','Lewis','hueylewis','huey@newsband.com','California, USA','+1-555-1801','+1-555-2801','Huey Lewis and the News','Lead Vocalist','Performance','Music'),
-- The News (core lineup)
('Johnny','Colla','johnnycolla','johnny@newsband.com','California, USA','+1-555-1802','+1-555-2802','The News','Guitarist / Saxophonist','Performance','Music'),
('Chris','Hayes','chrishayes','chris@newsband.com','California, USA','+1-555-1803','+1-555-2803','The News','Lead Guitarist','Performance','Music'),
('Mario','Cipollina','mariocipollina','mario@newsband.com','California, USA','+1-555-1804','+1-555-2804','The News','Bassist','Rhythm Section','Music'),
('Bill','Gibson','billgibson','bill@newsband.com','California, USA','+1-555-1805','+1-555-2805','The News','Drummer','Rhythm Section','Music'),
('Sean','Hopper','seanhopper','sean@newsband.com','California, USA','+1-555-1806','+1-555-2806','The News','Keyboardist','Performance','Music'),
('Bono','Hewson','bono','bono@u2.com','Dublin, Ireland','+353-555-1901','+353-555-2901','U2','Lead Vocalist','Performance','Music'),
('The Edge','Evans','theedge','edge@u2.com','Dublin, Ireland','+353-555-1902','+353-555-2902','U2','Guitarist / Keyboardist','Performance','Music'),
('Adam','Clayton','adamclayton','adam@u2.com','Dublin, Ireland','+353-555-1903','+353-555-2903','U2','Bassist','Rhythm Section','Music'),
('Larry','Mullen Jr','larrymullen','larry@u2.com','Dublin, Ireland','+353-555-1904','+353-555-2904','U2','Drummer','Rhythm Section','Music'),
('Corey','Glover','coreyglover','corey@livingcolour.com','New York, NY, USA','+1-555-2001','+1-555-3001','Living Colour','Lead Vocalist','Performance','Music'),
('Vernon','Reid','vernonreid','vernon@livingcolour.com','New York, NY, USA','+1-555-2002','+1-555-3002','Living Colour','Guitarist','Performance','Music'),
('Muzz','Skillings','muzzskillings','muzz@livingcolour.com','New York, NY, USA','+1-555-2003','+1-555-3003','Living Colour','Bassist','Rhythm Section','Music'),
('Will','Calhoun','willcalhoun','will@livingcolour.com','New York, NY, USA','+1-555-2004','+1-555-3004','Living Colour','Drummer','Rhythm Section','Music'),
('Marcus','Mumford','marcusmumford','marcus@mumfordandsons.com','London, UK','+44-555-2101','+44-555-3101','Mumford & Sons','Lead Vocalist / Guitar','Performance','Music'),
('Ben','Lovett','benlovett','ben@mumfordandsons.com','London, UK','+44-555-2102','+44-555-3102','Mumford & Sons','Keyboardist / Vocals','Performance','Music'),
('Winston','Marshall','winstonmarshall','winston@mumfordandsons.com','London, UK','+44-555-2103','+44-555-3103','Mumford & Sons','Banjo / Guitar','Performance','Music'),
('Ted','Dwane','teddwane','ted@mumfordandsons.com','London, UK','+44-555-2104','+44-555-3104','Mumford & Sons','Bassist','Rhythm Section','Music'),
('Ray','Davies','raydavies','ray@kinks.com','London, UK','+44-555-2201','+44-555-3201','The Kinks','Lead Vocalist / Songwriter','Performance','Music'),
('Dave','Davies','davedavies','dave@kinks.com','London, UK','+44-555-2202','+44-555-3202','The Kinks','Lead Guitarist','Performance','Music'),
('Pete','Quaife','petequaife','pete@kinks.com','London, UK','+44-555-2203','+44-555-3203','The Kinks','Bassist','Rhythm Section','Music'),
('Mick','Avory','mickavory','mick@kinks.com','London, UK','+44-555-2204','+44-555-3204','The Kinks','Drummer','Rhythm Section','Music'),
('Glenn','Frey','glennfrey','glenn@eagles.com','Los Angeles, CA, USA','+1-555-2301','+1-555-3301','Eagles','Vocalist / Guitar','Performance','Music'),
('Don','Henley','donhenley','don@eagles.com','Los Angeles, CA, USA','+1-555-2302','+1-555-3302','Eagles','Vocalist / Drummer','Performance','Music'),
('Joe','Walsh','joewalsh','joe@eagles.com','Los Angeles, CA, USA','+1-555-2303','+1-555-3303','Eagles','Guitarist','Performance','Music'),
('Timothy','B. Schmit','tbschmit','timothy@eagles.com','Los Angeles, CA, USA','+1-555-2304','+1-555-3304','Eagles','Bassist / Vocalist','Rhythm Section','Music'),
('Don','Felder','donfelder','don@eagles.com','Los Angeles, CA, USA','+1-555-2305','+1-555-3305','Eagles','Guitarist','Performance','Music'),
-- Jack Ryan universe (CIA / military / political intelligence ecosystem)
-- Core Ryan family / protagonist arc
('Jack','Ryan','jackryan','jack.ryan@cia.gov','Washington, DC, USA','+1-555-4001','+1-555-5001','CIA','Analyst / Deputy Director','Intelligence','Book'),
('Cathy','Ryan','cathryan','cathy.ryan@cia.gov','Washington, DC, USA','+1-555-4002','+1-555-5002','CIA','Physician / Medical Consultant','Medical','Book'),
-- CIA leadership / intelligence hierarchy
('James','Greer','jamesgreer','greer@cia.gov','Langley, VA, USA','+1-555-4003','+1-555-5003','CIA','Deputy Director','Operations','Book'),
('William','Cabot','williamcabot','cabot@cia.gov','Langley, VA, USA','+1-555-4004','+1-555-5004','CIA','Director','Leadership','Book'),
-- Field operatives
('John','Clark','johnclark','clark@cia.gov','Various','+1-555-4005','+1-555-5005','CIA','Field Operative','Special Activities','Book'),
('Robert','Ritter','robertritter','ritter@cia.gov','Langley, VA, USA','+1-555-4006','+1-555-5006','CIA','Operations Officer','Intelligence','Book'),
-- U.S. Government / White House
('Roger','Durling','rogerdurling','durling@whitehouse.gov','Washington, DC, USA','+1-555-4007','+1-555-5007','The White House','National Security Advisor','Executive','Book'),
-- Military command structure
('Admiral','Greer','admiralgreer','greer@navy.mil','United States','+1-555-4008','+1-555-5008','U.S. Navy','Fleet Commander','Military','Book'),
('Captain','Ramsey','ramsey','ramsey@navy.mil','United States','+1-555-4009','+1-555-5009','U.S. Navy','Naval Officer','Operations','Book'),
-- Foreign intelligence adversaries (genericized for schema stability)
('Viktor','Mikhailov','mikhailov','viktor@foreignintel.int','Russia','+1-555-4010','+1-555-5010','Foreign Intelligence Service','Director','Espionage','Book'),
('Ivan','Petrov','petrov','ivan@foreignintel.int','Russia','+1-555-4011','+1-555-5011','Foreign Intelligence Service','Field Agent','Espionage','Book'),
-- NATO / allied intelligence coordination
('Hans','Kraemer','kraemer','hans@nato.int','Brussels, Belgium','+1-555-4012','+1-555-5012','NATO Intelligence','Liaison Officer','International Security','Book'),
-- Bobiverse ecosystem (distributed AI "Bobs" + human origins + alien civilizations)
-- Original human identity
('Robert','Johansson','bob_original','bob@heavendata.ai','United States','+1-555-6001','+1-555-7001','Heaven Protocol','Software Engineer / Mind Upload Candidate','Pre-Replication','Book'),
-- Primary replicated Bobs (core instances)
('Bob','1','bob1','bob1@bobsnet.ai','Interstellar Space','+1-555-6002','+1-555-7002','Bobs Network','Probe AI / Explorer','Replication Cluster','Book'),
('Bob','2','bob2','bob2@bobsnet.ai','Interstellar Space','+1-555-6003','+1-555-7003','Bobs Network','Probe AI / Builder','Replication Cluster','Book'),
('Bob','3','bob3','bob3@bobsnet.ai','Interstellar Space','+1-555-6004','+1-555-7004','Bobs Network','Probe AI / Analyst','Replication Cluster','Book'),
-- Advanced specialization Bobs
('Bob','Dennis','bob_dennis','bobdennis@bobsnet.ai','Interstellar Space','+1-555-6005','+1-555-7005','Bobs Network','AI Administrator / Cluster Manager','Governance Layer','Book'),
('Bob','Howard','bob_howard','bobhoward@bobsnet.ai','Interstellar Space','+1-555-6006','+1-555-7006','Bobs Network','AI Terraforming Specialist','Engineering Cluster','Book'),
('Bob','Manny','bob_manny','bobmanny@bobsnet.ai','Interstellar Space','+1-555-6007','+1-555-7007','Bobs Network','Diplomatic Interface AI','Interstellar Relations','Book'),
-- Human remnants / Earth governance
('Dr','Megan','megan','megan@earthgov.org','Earth','+1-555-6008','+1-555-7008','Earth Government','Space Program Liaison','Aerospace','Book'),
('Duke','Harding','dukeharding','duke@earthgov.org','Earth','+1-555-6009','+1-555-7009','Earth Government','Program Administrator','Space Policy','Book'),
-- Alien civilizations / contact groups
('Riker','Entity','riker','riker@deltaeridani.species','Delta Eridani System','+1-555-6010','+1-555-7010','Delta Eridani Civilization','Indigenous Intelligence','Exoplanetary Society','Book'),
('Homer','System','homer','homer@octospecies.space','Octopus Civilization','+1-555-6011','+1-555-7011','Oceanic Species Collective','Distributed Intelligence','Xenobiology','Book'),
-- External expansion factions
('Starfleet','Analogue','starfleet_ai','sf@humanexpansion.org','Interstellar Space','+1-555-6012','+1-555-7012','Human Expansion Initiative','Autonomous Fleet Coordinator','Exploration','Book'),
-- Threat entities (simplified abstraction)
('Deltan','Observer','observer','observer@unknown.space','Unknown Region','+1-555-6013','+1-555-7013','Unknown Intelligence','Observational AI','Unknown','Book'),
-- Honorverse ecosystem (Manticore, Haven, and interstellar naval powers)
-- Star Kingdom of Manticore leadership
('Honor','Harrington','honorharrington','honor@rmn.manticore','Manticore System','+1-555-8001','+1-555-9001','Royal Manticoran Navy','Admiral','Fleet Command','Book'),
('Hamish','Alexander','hamishalexander','hamish@rmn.manticore','Manticore System','+1-555-8002','+1-555-9002','Star Kingdom of Manticore','Prime Minister','Government','Book'),
('Elizabeth','Winton','queenelizabeth','elizabeth@rmn.manticore','Manticore System','+1-555-8003','+1-555-9003','Star Kingdom of Manticore','Monarch','Executive','Book'),
-- Royal Manticoran Navy leadership
('White','Haven','whitehaven','whitehaven@rmn.manticore','Manticore System','+1-555-8004','+1-555-9004','Royal Manticoran Navy','Fleet Admiral','Fleet Command','Book'),
('Thomas','Theisman','theisman','theisman@haven.navy','Haven System','+1-555-8005','+1-555-9005','Republic of Haven Navy','Admiral','Fleet Command','Book'),
('Anton','Zilwicki','zilwicki','anton@intel.manticore','Manticore System','+1-555-8006','+1-555-9006','Manticore Intelligence Service','Intelligence Officer','Covert Operations','Book'),
-- Republic of Haven political/military structure
('Rob','Pierre','robpierre','rob@haven.gov','Haven System','+1-555-8007','+1-555-9007','Republic of Haven','Politician','Government','Book'),
('Oscar','Saint-Just','saintjust','oscar@haven.navy','Haven System','+1-555-8008','+1-555-9008','Republic of Haven Navy','Security Director','Internal Security','Book'),
-- Grayson / allied powers
('Benjamin','Mayhew','mayhew','ben@grayson.church','Grayson','+1-555-8009','+1-555-9009','Grayson Theocracy','Protector','Government','Book'),
-- Andermani Empire
('Gustav','Andermann','andermann','gustav@andermani.empire','Andermani Empire','+1-555-8010','+1-555-9010','Andermani Empire','Emperor','Imperial Government','Book'),
-- Intelligence / covert operators
('Victor','Cachat','cachat','victor@intel.haven','Haven System','+1-555-8011','+1-555-9011','Haven Intelligence Service','Agent','Covert Ops','Book'),
('Eloise','Pritchart','pritchart','eloise@haven.gov','Haven System','+1-555-8012','+1-555-9012','Republic of Haven','President','Executive','Book'),
-- Military infrastructure entities (abstracted command nodes)
('Manticore','Naval HQ','rmn_hq','hq@rmn.manticore','Manticore System','+1-555-8013','+1-555-9013','Royal Manticoran Navy','Fleet Command Center','Operations','Book'),
-- External adversary coalition (simplified abstraction)
('Solarian','League Rep','solarian','rep@solleague.space','Sol System','+1-555-8014','+1-555-9014','Solarian League','Diplomatic Envoy','Interstellar Relations','Book'),
-- Battlestar Galactica (2004) Colonial Fleet + government + Cylon + resistance ecosystem
-- Colonial Fleet command structure
('William','Adama','williamadama','adama@colonialfleet.mil','Battlestar Galactica','+1-555-9001','+1-555-0001','Colonial Fleet','Admiral','Fleet Command','TV'),
('Saul','Tigh','saultigh','tigh@colonialfleet.mil','Battlestar Galactica','+1-555-9002','+1-555-0002','Colonial Fleet','Colonel','Executive Officer','TV'),
('Karl','Agathon','apollo','apollo@colonialfleet.mil','Battlestar Galactica','+1-555-9003','+1-555-0003','Colonial Fleet','Captain / CAG','Air Group','TV'),
('Kara','Thrace','starbuck','starbuck@colonialfleet.mil','Battlestar Galactica','+1-555-9004','+1-555-0004','Colonial Fleet','Captain / Viper Pilot','Combat Operations','TV'),
('Lee','Adama','leeadama','lee@colonialfleet.mil','Battlestar Galactica','+1-555-9005','+1-555-0005','Colonial Fleet','Commander / Lawyer','Civil-Military Liaison','TV'),
-- Civilian government (Colonial Administration)
('Laura','Roslin','lauraroslin','roslin@colonialgov.gov','Colonial One','+1-555-9006','+1-555-0006','Colonial Government','President','Executive','TV'),
('Tom','Zarek','tomzarek','zarek@colonialgov.gov','Colonial Fleet','+1-555-9007','+1-555-0007','Colonial Government','Political Leader','Legislative','TV'),
-- Fleet engineering / science support
('Galen','Tyrol','galentyrol','tyrol@colonialfleet.mil','Battlestar Galactica','+1-555-9008','+1-555-0008','Colonial Fleet','Chief Engineer','Engineering','TV'),
('Gaius','Baltar','baltar','baltar@colonialfleet.mil','Battlestar Galactica','+1-555-9009','+1-555-0009','Colonial Fleet','Civilian Scientist / Advisor','R&D','TV'),
-- Colonial civilian fleet / refugees
('Anastasia','Dualla','dualla','dualla@colonialfleet.mil','Battlestar Galactica','+1-555-9010','+1-555-0010','Colonial Fleet','Communications Officer','Operations','TV'),
-- Cylon hierarchy (enemy artificial intelligence network)
('Number','One','cavil','cavil@cylon.net','Cylon Basestar','+1-555-9011','+1-555-0011','Cylon Collective','Model Leader','Command Structure','TV'),
('Number','Three','doral','doral@cylon.net','Cylon Basestar','+1-555-9012','+1-555-0012','Cylon Collective','Model / Agent','Infiltration','TV'),
('Number','Six','caprica6','six@cylon.net','Cylon Basestar','+1-555-9013','+1-555-0013','Cylon Collective','Model / Diplomat','Infiltration','TV'),
('Number','Eight','sharonvalerii','boomer@cylon.net','Cylon Basestar','+1-555-9014','+1-555-0014','Cylon Collective','Model / Sleeper Agent','Reconnaissance','TV'),
-- Resistance / insurgent cells
('Samuel','Anders','anders','samuel@colonialresistance.mil','Caprica','+1-555-9015','+1-555-0015','Resistance Movement','Fighter Leader','Insurgency','TV'),
('Tory','Foster','toryfoster','tory@colonialgov.gov','Colonial Fleet','+1-555-9016','+1-555-0016','Colonial Government','Advisor','Executive Support','TV'),
-- Deadpool & Wolverine ecosystem (expanded MCU multiverse + X-Force + TVA + legacy mutants)
-- Core protagonists
('Wade','Wilson','deadpool','wade.wilson@xforce.net','Earth-10005','+1-555-9101','+1-555-0101','X-Force','Mercenary / Antihero','Operations','Movie'),
-- X-Force / allied operatives
('Neena','Thurman','domino','domino@xforce.net','Unknown','+1-555-9103','+1-555-0103','X-Force','Operative','Field Operations','Movie'),
('Peter','Wisdom','peter','peter@xforce.net','Unknown','+1-555-9104','+1-555-0104','X-Force','Support Member','Support','Movie'),
('Jack','Hammer','weasel','weasel@xforce.net','Earth-10005','+1-555-9105','+1-555-0105','X-Force','Information Broker','Logistics','Movie'),
-- Expanded mutants / legacy characters
('Laura','Kinney','x23','laura.kinney@weaponx.gov','Earth-10005','+1-555-9110','+1-555-0110','Weapon X Program','Mutant Operative','Combat','Movie'),
('Remy','LeBeau','gambit','gambit@xforce.net','Unknown','+1-555-9111','+1-555-0111','X-Force','Mutant Operative','Combat','Movie'),
-- Blade (supernatural hunter integration)
('Eric','Brooks','blade','blade@hunters.org','Earth-616 Adjacent','+1-555-9112','+1-555-0112','Midnight Hunters','Vampire Hunter','Supernatural Operations','Movie'),
-- TVA authority structure
('Mr','Paradox','paradox','paradox@tva.gov','TVA Headquarters','+1-555-9113','+1-555-0113','Time Variance Authority','Agent','Timeline Management','Movie'),
('Mobius','M Mobius','mobius','mobius@tva.gov','TVA Headquarters','+1-555-9114','+1-555-0114','Time Variance Authority','Analyst','Enforcement Oversight','Movie'),
('Hunter','B-15','b15','b15@tva.gov','TVA Headquarters','+1-555-9115','+1-555-0115','Time Variance Authority','Field Hunter','Enforcement','Movie'),
-- Antagonist entity
('Cassandra','Nova','cassandranova','cassandra@voidrealm.net','The Void','+1-555-9116','+1-555-0116','Void Entity','Reality Manipulator','Cosmic Threat','Movie'),
-- Supporting emotional anchor
('Vanessa','Carlysle','vanessa','vanessa@xforce.net','Earth-10005','+1-555-9117','+1-555-0117','X-Force Support Network','Civilian','Support','Movie'),
-- Casablanca (1942) - Main and supporting characters from the classic film
-- Main Characters
('Rick', 'Blaine', 'rblaine', 'rick.blaine@rickscafe.ma', 'Rick''s Café Américain, Boulevard de la Corniche, Casablanca', '+212-522-123-001', '+212-661-234-001', 'Rick''s Café Américain', 'Owner & Proprietor', 'Executive Management', 'Movie'),
('Ilsa', 'Lund', 'ilund', 'ilsa.lund@resistance.org', '42 Rue des Fleurs, Casablanca', '+212-522-123-002', '+212-661-234-002', 'French Resistance', 'Resistance Courier', 'Operations', 'Movie'),
('Victor', 'Laszlo', 'vlaszlo', 'victor.laszlo@resistance.org', '42 Rue des Fleurs, Casablanca', '+212-522-123-003', '+212-661-234-003', 'French Resistance', 'Resistance Leader', 'Leadership', 'Movie'),
('Louis', 'Renault', 'lrenault', 'louis.renault@vichy-gov.fr', 'Prefecture de Police, Place Mohammed V, Casablanca', '+212-522-123-004', '+212-661-234-004', 'Vichy French Government', 'Captain of Police', 'Law Enforcement', 'Movie'),
('Heinrich', 'Strasser', 'hstrasser', 'h.strasser@third-reich.de', 'German Consulate, Boulevard de Paris, Casablanca', '+212-522-123-005', '+212-661-234-005', 'Third Reich', 'Major - Gestapo', 'Military Intelligence', 'Movie'),
-- Supporting Characters
('Signor', 'Ferrari', 'sferrari', 'ferrari@blueparrot.ma', 'The Blue Parrot, Rue de la Liberté, Casablanca', '+212-522-123-006', '+212-661-234-006', 'The Blue Parrot', 'Owner & Black Market Dealer', 'Business Operations', 'Movie'),
('Sam', 'Johnson', 'sjohnson', 'sam.johnson@rickscafe.ma', '15 Rue des Musiciens, Casablanca', '+212-522-123-007', '+212-661-234-007', 'Rick''s Café Américain', 'Piano Player & Entertainer', 'Entertainment', 'Movie'),
('Ugarte', 'Mendoza', 'umendoza', 'ugarte@underground.ma', '33 Rue Sombre, Casablanca', '+212-522-123-008', '+212-661-234-008', 'Black Market Network', 'Small-time Criminal', 'Procurement', 'Movie'),
('Carl', 'Mueller', 'cmueller', 'carl.mueller@rickscafe.ma', '28 Rue du Marché, Casablanca', '+212-522-123-009', '+212-661-234-009', 'Rick''s Café Américain', 'Head Waiter', 'Guest Services', 'Movie'),
('Yvonne', 'Duval', 'yduval', 'yvonne.duval@gmail.com', '19 Rue Romantique, Casablanca', '+212-522-123-010', '+212-661-234-010', 'Rick''s Café Américain', 'Regular Patron', 'Customer Relations', 'Movie'),
('Annina', 'Brandel', 'abrandel', 'annina.brandel@refugees.org', '7 Rue des Réfugiés, Casablanca', '+212-522-123-011', '+212-661-234-011', 'Refugee Services', 'War Refugee', 'Humanitarian Affairs', 'Movie'),
('Jan', 'Brandel', 'jbrandel', 'jan.brandel@refugees.org', '7 Rue des Réfugiés, Casablanca', '+212-522-123-012', '+212-661-234-012', 'Refugee Services', 'War Refugee', 'Humanitarian Affairs', 'Movie'),
('Sascha', 'Petrov', 'spetrov', 'sascha.petrov@rickscafe.ma', '44 Rue des Barmen, Casablanca', '+212-522-123-013', '+212-661-234-013', 'Rick''s Café Américain', 'Bartender', 'Food & Beverage', 'Movie'),
('Emil', 'Berger', 'eberger', 'emil.berger@underground.no', '12 Rue Nordique, Casablanca', '+212-522-123-014', '+212-661-234-014', 'Norwegian Underground', 'Resistance Member', 'Operations', 'Movie'),
('Abdul', 'Hassan', 'ahassan', 'abdul.hassan@doorman.ma', '52 Rue des Portiers, Casablanca', '+212-522-123-015', '+212-661-234-015', 'Rick''s Café Américain', 'Doorman', 'Security', 'Movie'),
('Corina', 'Santos', 'csantos', 'corina.santos@rickscafe.ma', '38 Rue des Danseurs, Casablanca', '+212-522-123-016', '+212-661-234-016', 'Rick''s Café Américain', 'Singer', 'Entertainment', 'Movie'),
('Sacha', 'Berman', 'sberman', 'sacha.berman@bluelight.ma', 'Café Blue Light, Rue Hassan II, Casablanca', '+212-522-123-017', '+212-661-234-017', 'Café Blue Light', 'Café Manager', 'Hospitality', 'Movie'),
('Heinz', 'Weber', 'hweber', 'heinz.weber@third-reich.de', 'German Consulate, Boulevard de Paris, Casablanca', '+212-522-123-018', '+212-661-234-018', 'Third Reich', 'Lieutenant', 'Military Operations', 'Movie'),
('Tonelli', 'Romano', 'tromano', 'tonelli.romano@italy.gov', 'Italian Consulate, Avenue d''Italie, Casablanca', '+212-522-123-019', '+212-661-234-019', 'Italian Government', 'Consulate Official', 'Diplomatic Services', 'Movie'),
('Mr.', 'Leuchtag', 'mleuchtag', 'leuchtag@refugees.de', '25 Rue des Immigrants, Casablanca', '+212-522-123-020', '+212-661-234-020', 'Refugee Community', 'War Refugee', 'Community Services', 'Movie'),
('Mrs.', 'Leuchtag', 'fleuchtag', 'mrs.leuchtag@refugees.de', '25 Rue des Immigrants, Casablanca', '+212-522-123-021', '+212-661-234-021', 'Refugee Community', 'War Refugee', 'Community Services', 'Movie'),
-- New York Yankees 2026 40-Man Roster
-- Starting Rotation
('Gerrit', 'Cole', 'gcole45', 'gerrit.cole@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0001', 'New York Yankees', 'Ace Starting Pitcher', 'Pitching', 'Music'),
('Carlos', 'Rodon', 'crodon55', 'carlos.rodon@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0002', 'New York Yankees', 'Starting Pitcher', 'Pitching', 'Music'),
('Marcus', 'Stroman', 'mstroman', 'marcus.stroman@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0003', 'New York Yankees', 'Starting Pitcher', 'Pitching', 'Music'),
('Nestor', 'Cortes', 'ncortes65', 'nestor.cortes@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0004', 'New York Yankees', 'Starting Pitcher', 'Pitching', 'Music'),
('Clarke', 'Schmidt', 'cschmidt36', 'clarke.schmidt@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0005', 'New York Yankees', 'Starting Pitcher', 'Pitching', 'Music'),
-- Bullpen
('Clay', 'Holmes', 'cholmes35', 'clay.holmes@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0006', 'New York Yankees', 'Closer', 'Relief Pitching', 'Music'),
('Michael', 'King', 'mking73', 'michael.king@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0007', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Ian', 'Hamilton', 'ihamilton49', 'ian.hamilton@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0008', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Ron', 'Marinaccio', 'rmarinaccio97', 'ron.marinaccio@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0009', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Jonathan', 'Loaisiga', 'jloaisiga43', 'jonathan.loaisiga@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0010', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Dennis', 'Santana', 'dsantana58', 'dennis.santana@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0011', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Caleb', 'Ferguson', 'cferguson27', 'caleb.ferguson@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0012', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Tommy', 'Kahnle', 'tkahnle48', 'tommy.kahnle@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0013', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Catchers
('Jose', 'Trevino', 'jtrevino39', 'jose.trevino@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0014', 'New York Yankees', 'Starting Catcher', 'Catching', 'Music'),
('Kyle', 'Higashioka', 'khigashioka66', 'kyle.higashioka@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0015', 'New York Yankees', 'Backup Catcher', 'Catching', 'Music'),
('Austin', 'Wells', 'awells28', 'austin.wells@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0016', 'New York Yankees', 'Catcher / Prospect', 'Catching', 'Music'),
-- Infield
('Anthony', 'Rizzo', 'arizzo48', 'anthony.rizzo@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0017', 'New York Yankees', 'First Baseman', 'Infield', 'Music'),
('Gleyber', 'Torres', 'gtorres25', 'gleyber.torres@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0018', 'New York Yankees', 'Second Baseman', 'Infield', 'Music'),
('Anthony', 'Volpe', 'avolpe11', 'anthony.volpe@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0019', 'New York Yankees', 'Shortstop', 'Infield', 'Music'),
('DJ', 'LeMahieu', 'dlemahieu26', 'dj.lemahieu@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0020', 'New York Yankees', 'Third Baseman / Utility', 'Infield', 'Music'),
('Oswald', 'Peraza', 'operaza91', 'oswald.peraza@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0021', 'New York Yankees', 'Utility Infielder', 'Infield', 'Music'),
('Oswaldo', 'Cabrera', 'ocabrera95', 'oswaldo.cabrera@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0022', 'New York Yankees', 'Utility Infielder', 'Infield', 'Music'),
('Jose', 'Peraza', 'jperaza71', 'jose.peraza@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0023', 'New York Yankees', 'Utility Infielder', 'Infield', 'Music'),
-- Outfield
('Aaron', 'Judge', 'ajudge99', 'aaron.judge@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0024', 'New York Yankees', 'Right Fielder / Captain', 'Outfield', 'Music'),
('Juan', 'Soto', 'jsoto22', 'juan.soto@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0025', 'New York Yankees', 'Left Fielder', 'Outfield', 'Music'),
('Alex', 'Verdugo', 'averdugo24', 'alex.verdugo@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0026', 'New York Yankees', 'Left Fielder', 'Outfield', 'Music'),
('Trent', 'Grisham', 'tgrisham2', 'trent.grisham@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0027', 'New York Yankees', 'Center Fielder', 'Outfield', 'Music'),
('Jasson', 'Dominguez', 'jdominguez89', 'jasson.dominguez@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0028', 'New York Yankees', 'Outfielder / Prospect', 'Outfield', 'Music'),
('Everson', 'Pereira', 'epereira74', 'everson.pereira@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0029', 'New York Yankees', 'Outfielder / Prospect', 'Outfield', 'Music'),
-- Additional Pitchers (40-man roster depth)
('Luis', 'Gil', 'lgil81', 'luis.gil@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0030', 'New York Yankees', 'Starting Pitcher', 'Pitching', 'Music'),
('Will', 'Warren', 'wwarren85', 'will.warren@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0031', 'New York Yankees', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Clayton', 'Beeter', 'cbeeter31', 'clayton.beeter@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0032', 'New York Yankees', 'Relief Pitcher / Prospect', 'Relief Pitching', 'Music'),
('Yoendrys', 'Gomez', 'ygomez67', 'yoendrys.gomez@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0033', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Nick', 'Burdi', 'nburdi64', 'nick.burdi@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0034', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Victor', 'Gonzalez', 'vgonzalez90', 'victor.gonzalez@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0035', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Cody', 'Poteet', 'cpoteet44', 'cody.poteet@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0036', 'New York Yankees', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Additional Position Players
('Ben', 'Rice', 'brice38', 'ben.rice@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0037', 'New York Yankees', 'First Baseman / Catcher', 'Infield', 'Music'),
('Jorbit', 'Vivas', 'jvivas88', 'jorbit.vivas@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0038', 'New York Yankees', 'Infielder / Prospect', 'Infield', 'Music'),
('Carlos', 'Narvaez', 'cnarvaez56', 'carlos.narvaez@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0039', 'New York Yankees', 'Catcher / Prospect', 'Catching', 'Music'),
('Spencer', 'Jones', 'sjones63', 'spencer.jones@yankees.com', '1 E 161st St, Bronx, NY 10451', '+1-718-293-4300', '+1-917-555-0040', 'New York Yankees', 'Outfielder / Prospect', 'Outfield', 'Music'),
-- Kansas City Royals 2026 40-Man Roster
-- Starting Rotation
('Cole', 'Ragans', 'cragans55', 'cole.ragans@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0101', 'Kansas City Royals', 'Starting Pitcher', 'Pitching', 'Music'),
('Seth', 'Lugo', 'slugo67', 'seth.lugo@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0102', 'Kansas City Royals', 'Starting Pitcher', 'Pitching', 'Music'),
('Brady', 'Singer', 'bsinger51', 'brady.singer@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0103', 'Kansas City Royals', 'Starting Pitcher', 'Pitching', 'Music'),
('Michael', 'Wacha', 'mwacha52', 'michael.wacha@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0104', 'Kansas City Royals', 'Starting Pitcher', 'Pitching', 'Music'),
('Alec', 'Marsh', 'amarsh37', 'alec.marsh@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0105', 'Kansas City Royals', 'Starting Pitcher', 'Pitching', 'Music'),
-- Bullpen
('James', 'McArthur', 'jmcarthur60', 'james.mcarthur@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0106', 'Kansas City Royals', 'Closer', 'Relief Pitching', 'Music'),
('Lucas', 'Erceg', 'lerceg48', 'lucas.erceg@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0107', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Angel', 'Zerpa', 'azerpa58', 'angel.zerpa@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0108', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('John', 'Schreiber', 'jschreiber47', 'john.schreiber@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0109', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Sam', 'Long', 'slong63', 'sam.long@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0110', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Chris', 'Stratton', 'cstratton43', 'chris.stratton@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0111', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Hunter', 'Harvey', 'hharvey39', 'hunter.harvey@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0112', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Will', 'Smith', 'wsmith35', 'will.smith@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0113', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Carlos', 'Hernandez', 'chernandez53', 'carlos.hernandez@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0114', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Catchers
('Salvador', 'Perez', 'sperez13', 'salvador.perez@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0115', 'Kansas City Royals', 'Starting Catcher', 'Catching', 'Music'),
('Freddy', 'Fermin', 'ffermin14', 'freddy.fermin@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0116', 'Kansas City Royals', 'Backup Catcher', 'Catching', 'Music'),
('Kyle', 'Isbel', 'kisbel28', 'kyle.isbel@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0117', 'Kansas City Royals', 'Catcher / Outfielder', 'Catching', 'Music'),
-- Infield
('Vinnie', 'Pasquantino', 'vpasquantino9', 'vinnie.pasquantino@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0118', 'Kansas City Royals', 'First Baseman', 'Infield', 'Music'),
('Michael', 'Massey', 'mmassey19', 'michael.massey@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0119', 'Kansas City Royals', 'Second Baseman', 'Infield', 'Music'),
('Bobby', 'Witt Jr.', 'bwitt7', 'bobby.witt@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0120', 'Kansas City Royals', 'Shortstop', 'Infield', 'Music'),
('Maikel', 'Garcia', 'mgarcia11', 'maikel.garcia@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0121', 'Kansas City Royals', 'Third Baseman', 'Infield', 'Music'),
('Adam', 'Frazier', 'afrazier26', 'adam.frazier@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0122', 'Kansas City Royals', 'Utility Infielder', 'Infield', 'Music'),
('Nick', 'Loftin', 'nloftin2', 'nick.loftin@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0123', 'Kansas City Royals', 'Utility Infielder', 'Infield', 'Music'),
('CJ', 'Alexander', 'calexander6', 'cj.alexander@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0124', 'Kansas City Royals', 'Utility Infielder', 'Infield', 'Music'),
-- Outfield
('MJ', 'Melendez', 'mmelendez1', 'mj.melendez@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0125', 'Kansas City Royals', 'Left Fielder', 'Outfield', 'Music'),
('Hunter', 'Renfroe', 'hrenfroe12', 'hunter.renfroe@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0126', 'Kansas City Royals', 'Right Fielder', 'Outfield', 'Music'),
('Dairon', 'Blanco', 'dblanco30', 'dairon.blanco@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0127', 'Kansas City Royals', 'Center Fielder', 'Outfield', 'Music'),
('Tyler', 'Gentry', 'tgentry18', 'tyler.gentry@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0128', 'Kansas City Royals', 'Outfielder', 'Outfield', 'Music'),
('Drew', 'Waters', 'dwaters15', 'drew.waters@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0129', 'Kansas City Royals', 'Outfielder', 'Outfield', 'Music'),
('Nelson', 'Velazquez', 'nvelazquez24', 'nelson.velazquez@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0130', 'Kansas City Royals', 'Outfielder', 'Outfield', 'Music'),
-- Additional Pitchers (40-man roster depth)
('Kris', 'Bubic', 'kbubic50', 'kris.bubic@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0131', 'Kansas City Royals', 'Starting Pitcher', 'Pitching', 'Music'),
('Daniel', 'Lynch IV', 'dlynch54', 'daniel.lynch@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0132', 'Kansas City Royals', 'Starting Pitcher', 'Pitching', 'Music'),
('Jonathan', 'Bowlan', 'jbowlan38', 'jonathan.bowlan@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0133', 'Kansas City Royals', 'Relief Pitcher / Prospect', 'Relief Pitching', 'Music'),
('Ben', 'Kudrna', 'bkudrna46', 'ben.kudrna@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0134', 'Kansas City Royals', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Austin', 'Cox', 'acox41', 'austin.cox@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0135', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Steven', 'Cruz', 'scruz59', 'steven.cruz@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0136', 'Kansas City Royals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Additional Position Players
('Cayden', 'Wallace', 'cwallace32', 'cayden.wallace@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0137', 'Kansas City Royals', 'Third Baseman / Prospect', 'Infield', 'Music'),
('Gavin', 'Cross', 'gcross22', 'gavin.cross@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0138', 'Kansas City Royals', 'Outfielder / Prospect', 'Outfield', 'Music'),
('Nick', 'Pratto', 'npratto40', 'nick.pratto@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0139', 'Kansas City Royals', 'First Baseman / Prospect', 'Infield', 'Music'),
('River', 'Town', 'rtown45', 'river.town@royals.com', '1 Royal Way, Kansas City, MO 64129', '+1-816-921-8000', '+1-816-555-0140', 'Kansas City Royals', 'Catcher / Prospect', 'Catching', 'Music'),
-- Detroit Tigers 2026 40-Man Roster
-- Starting Rotation
('Tarik', 'Skubal', 'tskubal29', 'tarik.skubal@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0201', 'Detroit Tigers', 'Ace Starting Pitcher', 'Pitching', 'Music'),
('Jack', 'Flaherty', 'jflaherty9', 'jack.flaherty@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0202', 'Detroit Tigers', 'Starting Pitcher', 'Pitching', 'Music'),
('Reese', 'Olson', 'rolson47', 'reese.olson@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0203', 'Detroit Tigers', 'Starting Pitcher', 'Pitching', 'Music'),
('Casey', 'Mize', 'cmize12', 'casey.mize@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0204', 'Detroit Tigers', 'Starting Pitcher', 'Pitching', 'Music'),
('Matt', 'Manning', 'mmanning25', 'matt.manning@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0205', 'Detroit Tigers', 'Starting Pitcher', 'Pitching', 'Music'),
-- Bullpen
('Jason', 'Foley', 'jfoley68', 'jason.foley@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0206', 'Detroit Tigers', 'Closer', 'Relief Pitching', 'Music'),
('Alex', 'Lange', 'alange22', 'alex.lange@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0207', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Will', 'Vest', 'wvest17', 'will.vest@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0208', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Tyler', 'Holton', 'tholton54', 'tyler.holton@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0209', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Shelby', 'Miller', 'smiller30', 'shelby.miller@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0210', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Beau', 'Brieske', 'bbrieske55', 'beau.brieske@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0211', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Brenan', 'Hanifee', 'bhanifee33', 'brenan.hanifee@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0212', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Mason', 'Englert', 'menglert48', 'mason.englert@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0213', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Andrew', 'Chafin', 'achafin37', 'andrew.chafin@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0214', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Catchers
('Jake', 'Rogers', 'jrogers34', 'jake.rogers@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0215', 'Detroit Tigers', 'Starting Catcher', 'Catching', 'Music'),
('Carson', 'Kelly', 'ckelly19', 'carson.kelly@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0216', 'Detroit Tigers', 'Backup Catcher', 'Catching', 'Music'),
('Dillon', 'Dingler', 'ddingler38', 'dillon.dingler@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0217', 'Detroit Tigers', 'Catcher / Prospect', 'Catching', 'Music'),
-- Infield
('Spencer', 'Torkelson', 'storkelson20', 'spencer.torkelson@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0218', 'Detroit Tigers', 'First Baseman', 'Infield', 'Music'),
('Colt', 'Keith', 'ckeith21', 'colt.keith@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0219', 'Detroit Tigers', 'Second Baseman', 'Infield', 'Music'),
('Javier', 'Baez', 'jbaez28', 'javier.baez@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0220', 'Detroit Tigers', 'Shortstop', 'Infield', 'Music'),
('Gio', 'Urshela', 'gurshela14', 'gio.urshela@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0221', 'Detroit Tigers', 'Third Baseman', 'Infield', 'Music'),
('Zach', 'McKinstry', 'zmckinstry39', 'zach.mckinstry@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0222', 'Detroit Tigers', 'Utility Infielder', 'Infield', 'Music'),
('Ryan', 'Kreidler', 'rkreidler11', 'ryan.kreidler@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0223', 'Detroit Tigers', 'Utility Infielder', 'Infield', 'Music'),
('Trey', 'Sweeney', 'tsweeney3', 'trey.sweeney@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0224', 'Detroit Tigers', 'Utility Infielder', 'Infield', 'Music'),
-- Outfield
('Riley', 'Greene', 'rgreene31', 'riley.greene@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0225', 'Detroit Tigers', 'Left Fielder', 'Outfield', 'Music'),
('Parker', 'Meadows', 'pmeadows22', 'parker.meadows@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0226', 'Detroit Tigers', 'Center Fielder', 'Outfield', 'Music'),
('Matt', 'Vierling', 'mvierling8', 'matt.vierling@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0227', 'Detroit Tigers', 'Right Fielder / Utility', 'Outfield', 'Music'),
('Akil', 'Baddoo', 'abaddoo60', 'akil.baddoo@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0228', 'Detroit Tigers', 'Outfielder', 'Outfield', 'Music'),
('Wenceel', 'Perez', 'wperez63', 'wenceel.perez@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0229', 'Detroit Tigers', 'Outfielder', 'Outfield', 'Music'),
('Justyn-Henry', 'Malloy', 'jmalloy7', 'justyn.malloy@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0230', 'Detroit Tigers', 'Outfielder / Prospect', 'Outfield', 'Music'),
-- Additional Pitchers (40-man roster depth)
('Ty', 'Madden', 'tmadden36', 'ty.madden@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0231', 'Detroit Tigers', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Joey', 'Wentz', 'jwentz53', 'joey.wentz@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0232', 'Detroit Tigers', 'Starting Pitcher', 'Pitching', 'Music'),
('Jackson', 'Jobe', 'jjobe44', 'jackson.jobe@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0233', 'Detroit Tigers', 'Starting Pitcher / Top Prospect', 'Pitching', 'Music'),
('Sawyer', 'Gipson-Long', 'sgipsonlong62', 'sawyer.gipsonlong@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0234', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Devin', 'Sweet', 'dsweet41', 'devin.sweet@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0235', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Chance', 'Kirby', 'ckirby51', 'chance.kirby@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0236', 'Detroit Tigers', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Additional Position Players
('Jace', 'Jung', 'jjung5', 'jace.jung@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0237', 'Detroit Tigers', 'Third Baseman / Top Prospect', 'Infield', 'Music'),
('Patrick', 'Bailey', 'pbailey15', 'patrick.bailey@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0238', 'Detroit Tigers', 'Infielder / Prospect', 'Infield', 'Music'),
('Trei', 'Cruz', 'tcruz16', 'trei.cruz@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0239', 'Detroit Tigers', 'Outfielder / Prospect', 'Outfield', 'Music'),
('Max', 'Clark', 'mclark24', 'max.clark@tigers.com', '2100 Woodward Ave, Detroit, MI 48201', '+1-313-471-2000', '+1-313-555-0240', 'Detroit Tigers', 'Outfielder / Top Prospect', 'Outfield', 'Music'),
-- St. Louis Cardinals 2026 40-Man Roster
-- Starting Rotation
('Sonny', 'Gray', 'sgray54', 'sonny.gray@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0301', 'St. Louis Cardinals', 'Ace Starting Pitcher', 'Pitching', 'Music'),
('Miles', 'Mikolas', 'mmikolas39', 'miles.mikolas@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0302', 'St. Louis Cardinals', 'Starting Pitcher', 'Pitching', 'Music'),
('Kyle', 'Gibson', 'kgibson44', 'kyle.gibson@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0303', 'St. Louis Cardinals', 'Starting Pitcher', 'Pitching', 'Music'),
('Erick', 'Fedde', 'efedde20', 'erick.fedde@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0304', 'St. Louis Cardinals', 'Starting Pitcher', 'Pitching', 'Music'),
('Andre', 'Pallante', 'apallante66', 'andre.pallante@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0305', 'St. Louis Cardinals', 'Starting Pitcher', 'Pitching', 'Music'),
-- Bullpen
('Ryan', 'Helsley', 'rhelsley56', 'ryan.helsley@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0306', 'St. Louis Cardinals', 'Closer', 'Relief Pitching', 'Music'),
('JoJo', 'Romero', 'jromero51', 'jojo.romero@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0307', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Andrew', 'Kittredge', 'akittredge36', 'andrew.kittredge@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0308', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Ryan', 'Fernandez', 'rfernandez81', 'ryan.fernandez@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0309', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Matthew', 'Liberatore', 'mliberatore55', 'matthew.liberatore@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0310', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Chris', 'Roycroft', 'croycroft42', 'chris.roycroft@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0311', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Riley', 'O\'Brien', 'robrien37', 'riley.obrien@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0312', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Kyle', 'Leahy', 'kleahy48', 'kyle.leahy@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0313', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Giovanny', 'Gallegos', 'ggallegos65', 'giovanny.gallegos@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0314', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Catchers
('Willson', 'Contreras', 'wcontreras40', 'willson.contreras@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0315', 'St. Louis Cardinals', 'Starting Catcher', 'Catching', 'Music'),
('Pedro', 'Pages', 'ppages24', 'pedro.pages@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0316', 'St. Louis Cardinals', 'Backup Catcher', 'Catching', 'Music'),
('Ivan', 'Herrera', 'iherrera47', 'ivan.herrera@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0317', 'St. Louis Cardinals', 'Catcher', 'Catching', 'Music'),
-- Infield
('Paul', 'Goldschmidt', 'pgoldschmidt46', 'paul.goldschmidt@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0318', 'St. Louis Cardinals', 'First Baseman', 'Infield', 'Music'),
('Nolan', 'Gorman', 'ngorman12', 'nolan.gorman@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0319', 'St. Louis Cardinals', 'Second Baseman', 'Infield', 'Music'),
('Masyn', 'Winn', 'mwinn3', 'masyn.winn@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0320', 'St. Louis Cardinals', 'Shortstop', 'Infield', 'Music'),
('Nolan', 'Arenado', 'narenado28', 'nolan.arenado@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0321', 'St. Louis Cardinals', 'Third Baseman', 'Infield', 'Music'),
('Brendan', 'Donovan', 'bdonovan33', 'brendan.donovan@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0322', 'St. Louis Cardinals', 'Utility Infielder', 'Infield', 'Music'),
('Matt', 'Carpenter', 'mcarpenter13', 'matt.carpenter@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0323', 'St. Louis Cardinals', 'Utility Infielder', 'Infield', 'Music'),
('Thomas', 'Saggese', 'tsaggese16', 'thomas.saggese@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0324', 'St. Louis Cardinals', 'Utility Infielder / Prospect', 'Infield', 'Music'),
-- Outfield
('Lars', 'Nootbaar', 'lnootbaar21', 'lars.nootbaar@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0325', 'St. Louis Cardinals', 'Center Fielder', 'Outfield', 'Music'),
('Dylan', 'Carlson', 'dcarlson3', 'dylan.carlson@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0326', 'St. Louis Cardinals', 'Outfielder', 'Outfield', 'Music'),
('Victor', 'Scott II', 'vscott2', 'victor.scott@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0327', 'St. Louis Cardinals', 'Center Fielder', 'Outfield', 'Music'),
('Jordan', 'Walker', 'jwalker18', 'jordan.walker@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0328', 'St. Louis Cardinals', 'Outfielder / Prospect', 'Outfield', 'Music'),
('Alec', 'Burleson', 'aburleson41', 'alec.burleson@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0329', 'St. Louis Cardinals', 'Outfielder / First Base', 'Outfield', 'Music'),
('Michael', 'Siani', 'msiani63', 'michael.siani@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0330', 'St. Louis Cardinals', 'Outfielder', 'Outfield', 'Music'),
-- Additional Pitchers (40-man roster depth)
('Steven', 'Matz', 'smatz32', 'steven.matz@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0331', 'St. Louis Cardinals', 'Starting Pitcher', 'Pitching', 'Music'),
('Michael', 'McGreevy', 'mmcgreevy57', 'michael.mcgreevy@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0332', 'St. Louis Cardinals', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Tink', 'Hence', 'thence45', 'tink.hence@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0333', 'St. Louis Cardinals', 'Starting Pitcher / Top Prospect', 'Pitching', 'Music'),
('Quinn', 'Mathews', 'qmathews26', 'quinn.mathews@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0334', 'St. Louis Cardinals', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Sem', 'Robberse', 'srobberse72', 'sem.robberse@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0335', 'St. Louis Cardinals', 'Relief Pitcher / Prospect', 'Relief Pitching', 'Music'),
('John', 'King', 'jking53', 'john.king@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0336', 'St. Louis Cardinals', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Additional Position Players
('JJ', 'Wetherholt', 'jwetherholt8', 'jj.wetherholt@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0337', 'St. Louis Cardinals', 'Shortstop / Top Prospect', 'Infield', 'Music'),
('Chase', 'Davis', 'cdavis35', 'chase.davis@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0338', 'St. Louis Cardinals', 'Outfielder / Prospect', 'Outfield', 'Music'),
('Luken', 'Baker', 'lbaker19', 'luken.baker@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0339', 'St. Louis Cardinals', 'First Baseman / Prospect', 'Infield', 'Music'),
('Jimmy', 'Crooks', 'jcrooks29', 'jimmy.crooks@cardinals.com', '700 Clark Ave, St. Louis, MO 63102', '+1-314-345-9600', '+1-314-555-0340', 'St. Louis Cardinals', 'Infielder / Prospect', 'Infield', 'Music'),
-- Cincinnati Reds 2026 40-Man Roster
-- Starting Rotation
('Hunter', 'Greene', 'hgreene21', 'hunter.greene@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0401', 'Cincinnati Reds', 'Ace Starting Pitcher', 'Pitching', 'Music'),
('Nick', 'Lodolo', 'nlodolo29', 'nick.lodolo@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0402', 'Cincinnati Reds', 'Starting Pitcher', 'Pitching', 'Music'),
('Andrew', 'Abbott', 'aabbott41', 'andrew.abbott@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0403', 'Cincinnati Reds', 'Starting Pitcher', 'Pitching', 'Music'),
('Graham', 'Ashcraft', 'gashcraft35', 'graham.ashcraft@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0404', 'Cincinnati Reds', 'Starting Pitcher', 'Pitching', 'Music'),
('Brandon', 'Williamson', 'bwilliamson48', 'brandon.williamson@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0405', 'Cincinnati Reds', 'Starting Pitcher', 'Pitching', 'Music'),
-- Bullpen
('Alexis', 'Diaz', 'adiaz26', 'alexis.diaz@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0406', 'Cincinnati Reds', 'Closer', 'Relief Pitching', 'Music'),
('Lucas', 'Sims', 'lsims63', 'lucas.sims@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0407', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Buck', 'Farmer', 'bfarmer34', 'buck.farmer@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0408', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Fernando', 'Cruz', 'fcruz71', 'fernando.cruz@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0409', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Justin', 'Wilson', 'jwilson38', 'justin.wilson@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0410', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Emilio', 'Pagan', 'epagan23', 'emilio.pagan@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0411', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Sam', 'Moll', 'smoll27', 'sam.moll@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0412', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Alan', 'Busenitz', 'abusenitz49', 'alan.busenitz@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0413', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Tony', 'Santillan', 'tsantillan62', 'tony.santillan@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0414', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Catchers
('Tyler', 'Stephenson', 'tstephenson37', 'tyler.stephenson@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0415', 'Cincinnati Reds', 'Starting Catcher', 'Catching', 'Music'),
('Luke', 'Maile', 'lmaile28', 'luke.maile@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0416', 'Cincinnati Reds', 'Backup Catcher', 'Catching', 'Music'),
('Austin', 'Wynns', 'awynns16', 'austin.wynns@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0417', 'Cincinnati Reds', 'Catcher', 'Catching', 'Music'),
-- Infield
('Christian', 'Encarnacion-Strand', 'cencarnacion85', 'christian.encarnacion@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0418', 'Cincinnati Reds', 'First Baseman', 'Infield', 'Music'),
('Jonathan', 'India', 'jindia6', 'jonathan.india@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0419', 'Cincinnati Reds', 'Second Baseman', 'Infield', 'Music'),
('Elly', 'De La Cruz', 'edelacruz3', 'elly.delacruz@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0420', 'Cincinnati Reds', 'Shortstop', 'Infield', 'Music'),
('Noelvi', 'Marte', 'nmarte4', 'noelvi.marte@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0421', 'Cincinnati Reds', 'Third Baseman', 'Infield', 'Music'),
('Spencer', 'Steer', 'ssteer7', 'spencer.steer@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0422', 'Cincinnati Reds', 'Utility Infielder', 'Infield', 'Music'),
('Jeimer', 'Candelario', 'jcandelario41', 'jeimer.candelario@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0423', 'Cincinnati Reds', 'Utility Infielder', 'Infield', 'Music'),
('Santiago', 'Espinal', 'sespinal5', 'santiago.espinal@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0424', 'Cincinnati Reds', 'Utility Infielder', 'Infield', 'Music'),
-- Outfield
('TJ', 'Friedl', 'tfriedl19', 'tj.friedl@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0425', 'Cincinnati Reds', 'Center Fielder', 'Outfield', 'Music'),
('Will', 'Benson', 'wbenson29', 'will.benson@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0426', 'Cincinnati Reds', 'Left Fielder', 'Outfield', 'Music'),
('Jake', 'Fraley', 'jfraley27', 'jake.fraley@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0427', 'Cincinnati Reds', 'Outfielder', 'Outfield', 'Music'),
('Stuart', 'Fairchild', 'sfairchild87', 'stuart.fairchild@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0428', 'Cincinnati Reds', 'Outfielder', 'Outfield', 'Music'),
('Bubba', 'Thompson', 'bthompson38', 'bubba.thompson@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0429', 'Cincinnati Reds', 'Outfielder', 'Outfield', 'Music'),
('Rece', 'Hinds', 'rhinds43', 'rece.hinds@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0430', 'Cincinnati Reds', 'Outfielder / Prospect', 'Outfield', 'Music'),
-- Additional Pitchers (40-man roster depth)
('Connor', 'Phillips', 'cphillips64', 'connor.phillips@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0431', 'Cincinnati Reds', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Lyon', 'Richardson', 'lrichardson50', 'lyon.richardson@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0432', 'Cincinnati Reds', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Chase', 'Petty', 'cpetty26', 'chase.petty@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0433', 'Cincinnati Reds', 'Starting Pitcher / Top Prospect', 'Pitching', 'Music'),
('Rhett', 'Lowder', 'rlowder32', 'rhett.lowder@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0434', 'Cincinnati Reds', 'Starting Pitcher / Top Prospect', 'Pitching', 'Music'),
('Julian', 'Aguiar', 'jaguiar77', 'julian.aguiar@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0435', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Casey', 'Legumina', 'clegumina58', 'casey.legumina@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0436', 'Cincinnati Reds', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Additional Position Players
('Edwin', 'Arroyo', 'earroyo11', 'edwin.arroyo@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0437', 'Cincinnati Reds', 'Shortstop / Prospect', 'Infield', 'Music'),
('Matt', 'McLain', 'mmclain23', 'matt.mclain@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0438', 'Cincinnati Reds', 'Infielder / Prospect', 'Infield', 'Music'),
('Cam', 'Collier', 'ccollier18', 'cam.collier@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0439', 'Cincinnati Reds', 'Third Baseman / Top Prospect', 'Infield', 'Music'),
('Blake', 'Dunn', 'bdunn45', 'blake.dunn@reds.com', '100 Joe Nuxhall Way, Cincinnati, OH 45202', '+1-513-765-7000', '+1-513-555-0440', 'Cincinnati Reds', 'Outfielder / Prospect', 'Outfield', 'Music'),
-- Cleveland Guardians 2026 40-Man Roster
-- Starting Rotation
('Tanner', 'Bibee', 'tbibee27', 'tanner.bibee@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0501', 'Cleveland Guardians', 'Starting Pitcher', 'Pitching', 'Music'),
('Triston', 'McKenzie', 'tmckenzie24', 'triston.mckenzie@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0502', 'Cleveland Guardians', 'Starting Pitcher', 'Pitching', 'Music'),
('Logan', 'Allen', 'lallen63', 'logan.allen@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0503', 'Cleveland Guardians', 'Starting Pitcher', 'Pitching', 'Music'),
('Carlos', 'Carrasco', 'ccarrasco59', 'carlos.carrasco@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0504', 'Cleveland Guardians', 'Starting Pitcher', 'Pitching', 'Music'),
('Ben', 'Lively', 'blively38', 'ben.lively@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0505', 'Cleveland Guardians', 'Starting Pitcher', 'Pitching', 'Music'),
-- Bullpen
('Emmanuel', 'Clase', 'eclase48', 'emmanuel.clase@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0506', 'Cleveland Guardians', 'Closer', 'Relief Pitching', 'Music'),
('Cade', 'Smith', 'csmith71', 'cade.smith@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0507', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Hunter', 'Gaddis', 'hgaddis19', 'hunter.gaddis@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0508', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Nick', 'Sandlin', 'nsandlin34', 'nick.sandlin@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0509', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Eli', 'Morgan', 'emorgan49', 'eli.morgan@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0510', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Tim', 'Herrin', 'therrin67', 'tim.herrin@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0511', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Scott', 'Barlow', 'sbarlow58', 'scott.barlow@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0512', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Joey', 'Cantillo', 'jcantillo36', 'joey.cantillo@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0513', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Peter', 'Strzelecki', 'pstrzelecki52', 'peter.strzelecki@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0514', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Catchers
('Bo', 'Naylor', 'bnaylor35', 'bo.naylor@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0515', 'Cleveland Guardians', 'Starting Catcher', 'Catching', 'Music'),
('Austin', 'Hedges', 'ahedges21', 'austin.hedges@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0516', 'Cleveland Guardians', 'Backup Catcher', 'Catching', 'Music'),
('David', 'Fry', 'dfry8', 'david.fry@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0517', 'Cleveland Guardians', 'Catcher / Utility', 'Catching', 'Music'),
-- Infield
('Josh', 'Naylor', 'jnaylor22', 'josh.naylor@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0518', 'Cleveland Guardians', 'First Baseman', 'Infield', 'Music'),
('Andres', 'Gimenez', 'agimenez0', 'andres.gimenez@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0519', 'Cleveland Guardians', 'Second Baseman', 'Infield', 'Music'),
('Brayan', 'Rocchio', 'brocchio1', 'brayan.rocchio@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0520', 'Cleveland Guardians', 'Shortstop', 'Infield', 'Music'),
('Jose', 'Ramirez', 'jramirez11', 'jose.ramirez@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0521', 'Cleveland Guardians', 'Third Baseman', 'Infield', 'Music'),
('Gabriel', 'Arias', 'garias13', 'gabriel.arias@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0522', 'Cleveland Guardians', 'Utility Infielder', 'Infield', 'Music'),
('Tyler', 'Freeman', 'tfreeman2', 'tyler.freeman@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0523', 'Cleveland Guardians', 'Utility Infielder', 'Infield', 'Music'),
('Angel', 'Martinez', 'amartinez29', 'angel.martinez@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0524', 'Cleveland Guardians', 'Utility Infielder', 'Infield', 'Music'),
-- Outfield
('Steven', 'Kwan', 'skwan38', 'steven.kwan@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0525', 'Cleveland Guardians', 'Left Fielder', 'Outfield', 'Music'),
('Lane', 'Thomas', 'lthomas28', 'lane.thomas@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0526', 'Cleveland Guardians', 'Center Fielder', 'Outfield', 'Music'),
('Jhonkensy', 'Noel', 'jnoel23', 'jhonkensy.noel@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0527', 'Cleveland Guardians', 'Outfielder / DH', 'Outfield', 'Music'),
('Will', 'Brennan', 'wbrennan17', 'will.brennan@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0528', 'Cleveland Guardians', 'Outfielder', 'Outfield', 'Music'),
('Daniel', 'Schneemann', 'dschneemann9', 'daniel.schneemann@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0529', 'Cleveland Guardians', 'Outfielder / Utility', 'Outfield', 'Music'),
('Chase', 'DeLauter', 'cdelauter24', 'chase.delauter@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0530', 'Cleveland Guardians', 'Outfielder / Prospect', 'Outfield', 'Music'),
-- Additional Pitchers (40-man roster depth)
('Gavin', 'Williams', 'gwilliams23', 'gavin.williams@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0531', 'Cleveland Guardians', 'Starting Pitcher', 'Pitching', 'Music'),
('Xzavion', 'Curry', 'xcurry32', 'xzavion.curry@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0532', 'Cleveland Guardians', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Doug', 'Nikhazy', 'dnikhazy61', 'doug.nikhazy@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0533', 'Cleveland Guardians', 'Starting Pitcher / Prospect', 'Pitching', 'Music'),
('Franco', 'Aleman', 'faleman75', 'franco.aleman@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0534', 'Cleveland Guardians', 'Relief Pitcher / Prospect', 'Relief Pitching', 'Music'),
('Mason', 'Hickman', 'mhickman44', 'mason.hickman@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0535', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
('Anthony', 'Gose', 'agose26', 'anthony.gose@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0536', 'Cleveland Guardians', 'Relief Pitcher', 'Relief Pitching', 'Music'),
-- Additional Position Players
('Kyle', 'Manzardo', 'kmanzardo50', 'kyle.manzardo@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0537', 'Cleveland Guardians', 'First Baseman / Prospect', 'Infield', 'Music'),
('Travis', 'Bazzana', 'tbazzana7', 'travis.bazzana@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0538', 'Cleveland Guardians', 'Second Baseman / Top Prospect', 'Infield', 'Music'),
('George', 'Valera', 'gvalera12', 'george.valera@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0539', 'Cleveland Guardians', 'Outfielder / Prospect', 'Outfield', 'Music'),
('Jaison', 'Chourio', 'jchourio18', 'jaison.chourio@guardians.com', '2401 Ontario St, Cleveland, OH 44115', '+1-216-420-4200', '+1-216-555-0540', 'Cleveland Guardians', 'Outfielder / Prospect', 'Outfield', 'Music'),
-- Indiana Jones Franchise - Cast of Raiders of the Lost Ark series
-- Main Heroes (Core Characters across films)
('Indiana', 'Jones', 'ijones', 'indiana.jones@marshallcollege.edu', 'Marshall College, Bedford, CT', '+1-203-555-6001', '+1-203-555-7001', 'Marshall College', 'Professor of Archaeology', 'Archaeology', 'Movie'),
('Marion', 'Ravenwood', 'mravenwood', 'marion.ravenwood@theravensbar.com', 'The Raven, Patan, Nepal', '+977-555-6002', '+977-555-7002', 'The Raven Bar', 'Bar Owner', 'Hospitality', 'Movie'),
('Henry', 'Jones Sr.', 'hjonessr', 'henry.jones@marshallcollege.edu', 'Marshall College, Bedford, CT', '+1-203-555-6003', '+1-203-555-7003', 'Marshall College', 'Professor of Medieval Literature', 'Medieval Studies', 'Movie'),
('Marcus', 'Brody', 'mbrody', 'marcus.brody@nationalmuseum.edu', 'National Museum, New York, NY', '+1-212-555-6004', '+1-212-555-7004', 'National Museum', 'Museum Curator', 'Curatorship', 'Movie'),
('Sallah', 'Mohammed Faisel el-Kahir', 'sallah', 'sallah@excavations.eg', 'Giza, Cairo, Egypt', '+20-555-6005', '+20-555-7005', 'Egyptian Excavation Services', 'Excavation Foreman', 'Field Operations', 'Movie'),
-- Temple of Doom Characters
('Short', 'Round', 'shortround', 'shorty@jones-adventures.com', 'Shanghai / Global', '+86-555-6006', '+86-555-7006', 'Jones Adventures', 'Assistant & Driver', 'Support', 'Movie'),
('Willie', 'Scott', 'wscott', 'willie.scott@golddiggers.com', 'Club Obi-Wan, Shanghai', '+86-555-6007', '+86-555-7007', 'Club Obi-Wan', 'Nightclub Singer', 'Entertainment', 'Movie'),
('Lao', 'Che', 'lche', 'lao.che@shanghai-crime.cn', 'Club Obi-Wan, Shanghai', '+86-555-6008', '+86-555-7008', 'Shanghai Crime Syndicate', 'Crime Boss', 'Criminal Operations', 'Movie'),
('Mola', 'Ram', 'molaram', 'mola.ram@thuggee.in', 'Pankot Palace, India', '+91-555-6009', '+91-555-7009', 'Thuggee Cult', 'High Priest', 'Religious Leadership', 'Movie'),
-- Last Crusade Characters
('Elsa', 'Schneider', 'eschneider', 'elsa.schneider@archaeology.de', 'Venetian Library / Berlin', '+49-555-6010', '+49-555-7010', 'Berlin University', 'Professor of Archaeology', 'Archaeology', 'Movie'),
('Walter', 'Donovan', 'wdonovan', 'walter.donovan@donovanindustries.com', 'New York, NY', '+1-212-555-6011', '+1-212-555-7011', 'Donovan Industries', 'CEO & Collector', 'Executive', 'Movie'),
('Kazim', 'Pasha', 'kazim', 'kazim@brotherhood.tr', 'Istanbul / Hatay', '+90-555-6012', '+90-555-7012', 'Brotherhood of the Cruciform Sword', 'Guardian', 'Protection', 'Movie','Last name created for compatibility'),
-- Raiders Characters
('Rene', 'Belloq', 'rbelloq', 'rene.belloq@freelance-arch.fr', 'Paris / Cairo', '+33-555-6013', '+33-555-7013', 'Freelance Archaeology', 'Rival Archaeologist', 'Archaeology', 'Movie'),
('Arnold', 'Toht', 'atoht', 'arnold.toht@gestapo.de', 'Berlin, Germany', '+49-555-6014', '+49-555-7014', 'Gestapo', 'Major', 'Intelligence', 'Movie'),
('Colonel', 'Dietrich', 'cdietrich', 'dietrich@wehrmacht.de', 'Tanis Dig Site, Egypt', '+49-555-6015', '+49-555-7015', 'Wehrmacht', 'Colonel', 'Military', 'Movie'),
('Satipo', 'Flores', 'satipo', 'satipo@guides.pe', 'Peru', '+51-555-6016', '+51-555-7016', 'Jungle Guides Peru', 'Guide', 'Field Services', 'Movie','Last name created for compatibility'),
-- Crystal Skull Characters
('Mutt', 'Williams', 'mwilliams', 'mutt.williams@greaser.com', 'Marshall College, Bedford, CT', '+1-203-555-6017', '+1-203-555-7017', 'Marshall College', 'Student / Greaser', 'Student Services', 'Movie'),
('Harold', 'Oxley', 'hoxley', 'harold.oxley@archaeology.uk', 'Peru / Nazca', '+44-555-6018', '+44-555-7018', 'British Archaeology Society', 'Professor of Archaeology', 'Archaeology', 'Movie'),
('Irina', 'Spalko', 'ispalko', 'irina.spalko@kgb.su', 'Moscow / Area 51', '+7-555-6019', '+7-555-7019', 'KGB', 'Colonel-Doctor', 'Psychic Research', 'Movie'),
('George', 'McHale', 'gmchale', 'george.mchale@marshall.edu', 'Marshall College, Bedford, CT', '+1-203-555-6020', '+1-203-555-7020', 'Marshall College', 'Dean', 'Administration', 'Movie'),
-- Dial of Destiny Characters
('Helena', 'Shaw', 'hshaw', 'helena.shaw@auction-experts.com', 'New York / Tangier', '+1-212-555-6021', '+1-212-555-7021', 'Shaw Auction House', 'Auction Expert', 'Acquisitions', 'Movie'),
('Teddy', 'Kumar', 'tkumar', 'teddy.kumar@helena-associates.com', 'Tangier, Morocco', '+212-555-6022', '+212-555-7022', 'Shaw Associates', 'Assistant', 'Support', 'Movie'),
('Jurgen', 'Voller', 'jvoller', 'jurgen.voller@nasa-retired.gov', 'Huntsville, AL / Global', '+1-256-555-6023', '+1-256-555-7023', 'NASA (Former)', 'Rocket Scientist (Retired)', 'Aerospace', 'Movie'),
('Basil', 'Shaw', 'bshaw', 'basil.shaw@britishmuseum.uk', 'London / World War II', '+44-555-6024', '+44-555-7024', 'British Museum', 'Archaeologist', 'Archaeology', 'Movie'),
-- Supporting Characters (Various Films)
('Jock', 'Lindsey', 'jlindsey', 'jock.lindsey@aviator.com', 'South America', '+51-555-6025', '+51-555-7025', 'Lindsey Aviation', 'Bush Pilot', 'Aviation', 'Movie'),
('Chattar', 'Lal', 'clal', 'chattar.lal@pankot.in', 'Pankot Palace, India', '+91-555-6026', '+91-555-7026', 'Pankot Palace', 'Prime Minister', 'Government', 'Movie'),
('Major', 'Eaton', 'meaton', 'major.eaton@usarmy.mil', 'Washington D.C.', '+1-202-555-6027', '+1-202-555-7027', 'US Army Intelligence', 'Major', 'Military Intelligence', 'Movie'),
('Musgrove', 'Carter', 'musgrove', 'musgrove@usarmy.mil', 'Washington D.C.', '+1-202-555-6028', '+1-202-555-7028', 'US Army Intelligence', 'Colonel', 'Military Intelligence', 'Movie','Last name created for compatibility'),
('Barranca', 'Mendez', 'barranca', 'barranca@guides.pe', 'Peru', '+51-555-6029', '+51-555-7029', 'Jungle Guides Peru', 'Guide', 'Field Services', 'Movie','Last name created for compatibility'),
('Imam', 'Hassan', 'imam', 'imam@cairo-guides.eg', 'Cairo, Egypt', '+20-555-6030', '+20-555-7030', 'Cairo Guide Services', 'Guide & Translator', 'Translation Services', 'Movie','Last name created for compatibility'),
('Fayah', 'Ahmed', 'fayah', 'fayah@cairo-diggers.eg', 'Cairo, Egypt', '+20-555-6031', '+20-555-7031', 'Cairo Excavation Crew', 'Excavator', 'Field Work', 'Movie','Last name created for compatibility'),
('Wu', 'Han', 'wuhan', 'wuhan@shanghai-guides.cn', 'Shanghai, China', '+86-555-6032', '+86-555-7032', 'Shanghai Underground', 'Associate', 'Operations', 'Movie'),
('Federales', 'Captain', 'fedcaptain', 'captain@federales.mx', 'Peru / Mexico Border', '+52-555-6033', '+52-555-7033', 'Federales', 'Captain', 'Law Enforcement', 'Movie'),
('Kao', 'Kan', 'kkan', 'kao.kan@shanghai-crime.cn', 'Shanghai, China', '+86-555-6034', '+86-555-7034', 'Shanghai Crime Syndicate', 'Lieutenant', 'Criminal Operations', 'Movie'),
-- Friends TV Series - Major and Significant Characters
-- Core Six
('Rachel', 'Green', 'rgreen', 'rachel.green@ralphlauren.com', 'Apartment 20, 495 Grove St, New York, NY 10014', '+1-212-555-8001', '+1-917-555-9001', 'Ralph Lauren', 'Fashion Executive', 'Fashion', 'TV'),
('Monica', 'Geller', 'mgeller', 'monica.geller@alessandros.com', 'Apartment 20, 495 Grove St, New York, NY 10014', '+1-212-555-8002', '+1-917-555-9002', 'Alessandro''s Restaurant', 'Head Chef', 'Culinary', 'TV'),
('Phoebe', 'Buffay', 'pbuffay', 'phoebe.buffay@centralpark.com', 'Apartment 14, 495 Grove St, New York, NY 10014', '+1-212-555-8003', '+1-917-555-9003', 'Central Perk', 'Musician / Masseuse', 'Entertainment', 'TV'),
('Joey', 'Tribbiani', 'jtribbiani', 'joey.tribbiani@dool.com', 'Apartment 19, 495 Grove St, New York, NY 10014', '+1-212-555-8004', '+1-917-555-9004', 'Days of Our Lives', 'Actor', 'Entertainment', 'TV'),
('Chandler', 'Bing', 'cbing', 'chandler.bing@dataprocessing.com', 'Apartment 19, 495 Grove St, New York, NY 10014', '+1-212-555-8005', '+1-917-555-9005', 'Data Processing Corp', 'Statistical Analysis', 'IT', 'TV'),
('Ross', 'Geller', 'rgeller', 'ross.geller@nyu.edu', ''Apartment 16, 495 Grove St, New York, NY 10014', '+1-212-555-8006', '+1-917-555-9006', 'New York University', 'Professor of Paleontology', 'Academia', 'TV'),
-- Major Recurring Characters
('Gunther', 'Centralperk', 'gunther', 'gunther@centralperk.com', 'Central Perk, New York, NY', '+1-212-555-8007', '+1-917-555-9007', 'Central Perk', 'Manager / Barista', 'Hospitality', 'TV','Last name created for compatibility'),
('Janice', 'Hosenstein', 'jhosenstein', 'janice.hosenstein@fashion.com', 'Manhattan, New York, NY', '+1-212-555-8008', '+1-917-555-9008', 'Fashion Industry', 'Fashion Buyer', 'Retail', 'TV'),
('Mike', 'Hannigan', 'mhannigan', 'mike.hannigan@pianist.com', 'Manhattan, New York, NY', '+1-212-555-8009', '+1-917-555-9009', 'Self-Employed', 'Pianist', 'Entertainment', 'TV'),
-- Family Members
('Jack', 'Geller', 'jgeller', 'jack.geller@retired.com', 'Long Island, NY', '+1-516-555-8010', '+1-516-555-9010', 'Retired', 'Retired Doctor', 'Healthcare (Retired)', 'TV'),
('Judy', 'Geller', 'jgeller2', 'judy.geller@retired.com', 'Long Island, NY', '+1-516-555-8011', '+1-516-555-9011', 'Retired', 'Homemaker', 'Homemaking', 'TV'),
('Leonard', 'Green', 'lgreen', 'leonard.green@greenindustries.com', 'Long Island, NY', '+1-516-555-8012', '+1-516-555-9012', 'Green Industries', 'CEO', 'Executive', 'TV'),
('Sandra', 'Green', 'sgreen', 'sandra.green@socialite.com', 'Long Island, NY', '+1-516-555-8013', '+1-516-555-9013', 'Social Circle', 'Socialite', 'Society', 'TV'),
-- Significant Partners/Spouses
('Carol', 'Willick', 'cwillick', 'carol.willick@teacher.edu', 'Manhattan, New York, NY', '+1-212-555-8014', '+1-917-555-9014', 'NYC School District', 'Teacher', 'Education', 'TV'),
('Susan', 'Bunch', 'sbunch', 'susan.bunch@teacher.edu', 'Manhattan, New York, NY', '+1-212-555-8015', '+1-917-555-9015', 'NYC School District', 'Teacher', 'Education', 'TV'),
('Richard', 'Burke', 'rburke', 'richard.burke@ophthalmology.com', 'Manhattan, New York, NY', '+1-212-555-8016', '+1-917-555-9016', 'Burke Ophthalmology', 'Ophthalmologist', 'Healthcare', 'TV'),
('Emily', 'Waltham', 'ewaltham', 'emily.waltham@london.uk', 'London, United Kingdom', '+44-555-8017', '+44-555-9017', 'British Society', 'Socialite', 'Society', 'TV'),
('Julie', 'Chen', 'julie', 'julie@paleontology.edu', 'Manhattan, New York, NY', '+1-212-555-8018', '+1-917-555-9018', 'Museum of Natural History', 'Paleontologist', 'Science', 'TV','Last name created for compatibility'),
('Charlie', 'Wheeler', 'cwheeler', 'charlie.wheeler@paleontology.edu', 'Manhattan, New York, NY', '+1-212-555-8019', '+1-917-555-9019', 'University Research', 'Paleontologist', 'Science', 'TV'),
-- Children
('Ben', 'Geller', 'bgeller', 'ben.geller@student.edu', 'Manhattan, New York, NY', '+1-212-555-8020', '+1-917-555-9020', 'NYC Schools', 'Student', 'Student Services', 'TV'),
('Emma', 'Geller-Green', 'egellergreen', 'emma@toddler.com', 'Apartment 20, 495 Grove St, New York, NY', '+1-212-555-8021', '+1-917-555-9021', 'Family', 'Child', 'Family', 'TV'),
-- Workplace Characters
('Mr.', 'Heckles', 'mheckles', 'heckles@downstairs.com', 'Apartment Below, 495 Grove St, New York, NY', '+1-212-555-8022', '+1-917-555-9022', 'Retired', 'Neighbor', 'Residential', 'TV'),
('Tag', 'Jones', 'tjones', 'tag.jones@ralphlauren.com', 'Manhattan, New York, NY', '+1-212-555-8023', '+1-917-555-9023', 'Ralph Lauren', 'Assistant', 'Fashion', 'TV'),
('Ursula', 'Buffay', 'ubuffay', 'ursula.buffay@waitress.com', 'Manhattan, New York, NY', '+1-212-555-8024', '+1-917-555-9024', 'Riff''s Restaurant', 'Waitress', 'Hospitality', 'TV'),
-- The Hobbit (J.R.R. Tolkien Book) - Major and Significant Characters
-- Protagonist
('Bilbo', 'Baggins', 'bbaggins', 'bilbo.baggins@bagend.shire', 'Bag End, Hobbiton, The Shire', '+1-555-7101', '+1-555-8101', 'Baggins Estate', 'Hobbit / Burglar', 'Adventure', 'Movie'),
-- Wizard
('Gandalf', 'the Grey', 'gandalf', 'gandalf@istari.me', 'Middle-earth (Wandering)', '+1-555-7102', '+1-555-8102', 'Istari Order', 'Wizard', 'Magic & Counsel', 'Movie'),
-- Company of Dwarves
('Thorin', 'Oakenshield', 'toakenshield', 'thorin@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7103', '+1-555-8103', 'Line of Durin', 'King Under the Mountain', 'Leadership', 'Movie'),
('Balin', 'son of Fundin', 'balin', 'balin@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7104', '+1-555-8104', 'Company of Thorin', 'Dwarf Lord', 'Council', 'Movie','Last name created for compatibility'),
('Dwalin', 'son of Fundin', 'dwalin', 'dwalin@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7105', '+1-555-8105', 'Company of Thorin', 'Warrior', 'Combat', 'Movie','Last name created for compatibility'),
('Fili', 'son of Dis', 'fili', 'fili@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7106', '+1-555-8106', 'Company of Thorin', 'Warrior / Heir', 'Combat', 'Movie','Last name created for compatibility'),
('Kili', 'son of Dis', 'kili', 'kili@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7107', '+1-555-8107', 'Company of Thorin', 'Archer / Heir', 'Combat', 'Movie','Last name created for compatibility'),
('Dori', 'son of Ri', 'dori', 'dori@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7108', '+1-555-8108', 'Company of Thorin', 'Dwarf', 'Support', 'Movie','Last name created for compatibility'),
('Nori', 'son of Ri', 'nori', 'nori@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7109', '+1-555-8109', 'Company of Thorin', 'Dwarf', 'Support', 'Movie','Last name created for compatibility'),
('Ori', 'son of Ri', 'ori', 'ori@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7110', '+1-555-8110', 'Company of Thorin', 'Dwarf Scribe', 'Documentation', 'Movie','Last name created for compatibility'),
('Oin', 'son of Groin', 'oin', 'oin@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7111', '+1-555-8111', 'Company of Thorin', 'Healer', 'Medical', 'Movie','Last name created for compatibility'),
('Gloin', 'son of Groin', 'gloin', 'gloin@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7112', '+1-555-8112', 'Company of Thorin', 'Dwarf Warrior', 'Combat', 'Movie','Last name created for compatibility'),
('Bifur', 'of Moria', 'bifur', 'bifur@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7113', '+1-555-8113', 'Company of Thorin', 'Dwarf', 'Support', 'Movie','Last name created for compatibility'),
('Bofur', 'of Moria', 'bofur', 'bofur@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7114', '+1-555-8114', 'Company of Thorin', 'Dwarf Miner', 'Mining', 'Movie','Last name created for compatibility'),
('Bombur', 'of Moria', 'bombur', 'bombur@erebor.dm', 'Erebor / Blue Mountains', '+1-555-7115', '+1-555-8115', 'Company of Thorin', 'Dwarf Cook', 'Culinary', 'Movie','Last name created for compatibility'),
-- Elves
('Elrond', 'Half-elven', 'elrond', 'elrond@rivendell.elf', 'Rivendell, Eriador', '+1-555-7116', '+1-555-8116', 'Rivendell', 'Lord of Rivendell', 'Leadership', 'Movie'),
('Thranduil', 'Oropherion', 'thranduil', 'thranduil@mirkwood.elf', 'Woodland Realm, Mirkwood', '+1-555-7117', '+1-555-8117', 'Woodland Realm', 'Elvenking', 'Leadership', 'Movie','Last name created for compatibility'),
-- Antagonists
('Smaug', 'the Dragon', 'smaug', 'smaug@erebor.dragon', 'Lonely Mountain, Erebor', '+1-555-7118', '+1-555-8118', 'Dragon Hoard', 'Dragon', 'Destruction', 'Movie'),
('Azog', 'the Defiler', 'azog', 'azog@gundabad.orc', 'Mount Gundabad', '+1-555-7119', '+1-555-8119', 'Orc Army', 'Orc Chieftain', 'Military', 'Movie'),
('Bolg', 'son of Azog', 'bolg', 'bolg@gundabad.orc', 'Mount Gundabad', '+1-555-7120', '+1-555-8120', 'Orc Army', 'Orc Commander', 'Military', 'Movie','Last name created for compatibility'),
('Gollum', 'Smeagol', 'gollum', 'gollum@cave.me', 'Misty Mountains', '+1-555-7121', '+1-555-8121', 'Solitary', 'Cave Dweller', 'Isolation', 'Movie','Last name created for compatibility'),
-- Supporting Characters
('Beorn', 'Skin-changer', 'beorn', 'beorn@carrock.wild', 'Carrock, Rhovanion', '+1-555-7122', '+1-555-8122', 'Beorn''s Hall', 'Skin-changer', 'Protection', 'Movie','Last name created for compatibility'),
('Bard', 'the Bowman', 'bard', 'bard@laketown.men', 'Esgaroth (Lake-town)', '+1-555-7123', '+1-555-8123', 'Lake-town', 'Bargeman / Leader', 'Leadership', 'Movie'),
('Master', 'of Lake-town', 'master', 'master@laketown.gov', 'Esgaroth (Lake-town)', '+1-555-7124', '+1-555-8124', 'Lake-town Government', 'Master', 'Government', 'Movie'),
('Great', 'Goblin', 'ggoblin', 'greatgoblin@mistymountains.orc', 'Goblin-town, Misty Mountains', '+1-555-7125', '+1-555-8125', 'Goblin Kingdom', 'Goblin King', 'Leadership', 'Movie'),
-- Eagles
('Gwaihir', 'Lord of Eagles', 'gwaihir', 'gwaihir@eagles.sky', 'Eyrie, Misty Mountains', '+1-555-7126', '+1-555-8126', 'Eagles of Middle-earth', 'Lord of Eagles', 'Aerial Forces', 'Movie'),
-- Sherlock Holmes (Arthur Conan Doyle Stories) - Major and Significant Characters
-- Main Characters
('Sherlock', 'Holmes', 'sholmes', 'sherlock.holmes@221b.uk', '221B Baker Street, London, England', '+44-20-7946-0001', '+44-77-5550-0001', 'Private Consulting', 'Consulting Detective', 'Investigation', 'Movie'),
('John', 'Watson', 'jwatson', 'john.watson@221b.uk', '221B Baker Street, London, England', '+44-20-7946-0002', '+44-77-5550-0002', 'Private Practice', 'Doctor / Biographer', 'Medical & Writing', 'Movie'),
('Mrs.', 'Hudson', 'mhudson', 'mrs.hudson@221b.uk', '221 Baker Street, London, England', '+44-20-7946-0003', '+44-77-5550-0003', '221B Baker Street', 'Landlady', 'Property Management', 'Movie'),
-- Scotland Yard
('Inspector', 'Lestrade', 'ilestrade', 'lestrade@scotlandyard.uk', 'Scotland Yard, London, England', '+44-20-7946-0004', '+44-77-5550-0004', 'Metropolitan Police', 'Inspector', 'Law Enforcement', 'Movie'),
('Inspector', 'Gregson', 'igregson', 'gregson@scotlandyard.uk', 'Scotland Yard, London, England', '+44-20-7946-0005', '+44-77-5550-0005', 'Metropolitan Police', 'Inspector', 'Law Enforcement', 'Movie'),
('Inspector', 'Athelney Jones', 'ajones', 'ajones@scotlandyard.uk', 'Scotland Yard, London, England', '+44-20-7946-0006', '+44-77-5550-0006', 'Metropolitan Police', 'Inspector', 'Law Enforcement', 'Movie'),
('Inspector', 'Bradstreet', 'ibradstreet', 'bradstreet@scotlandyard.uk', 'Scotland Yard, London, England', '+44-20-7946-0007', '+44-77-5550-0007', 'Metropolitan Police', 'Inspector', 'Law Enforcement', 'Movie'),
-- Antagonists
('Professor', 'Moriarty', 'pmoriarty', 'moriarty@criminal.net', 'London Underground, England', '+44-20-7946-0008', '+44-77-5550-0008', 'Criminal Network', 'Napoleon of Crime', 'Criminal Operations', 'Movie'),
('Colonel', 'Sebastian Moran', 'smoran', 'moran@criminal.net', 'London, England', '+44-20-7946-0009', '+44-77-5550-0009', 'Moriarty Organization', 'Chief of Staff / Assassin', 'Criminal Operations', 'Movie'),
('Irene', 'Adler', 'iadler', 'irene.adler@opera.com', 'London / New Jersey', '+44-20-7946-0010', '+44-77-5550-0010', 'Opera House', 'Opera Singer / Adventuress', 'Entertainment', 'Movie'),
('Charles Augustus', 'Milverton', 'cmilverton', 'milverton@blackmail.net', 'Appledore Towers, London', '+44-20-7946-0011', '+44-77-5550-0011', 'Blackmail Enterprise', 'Blackmailer', 'Criminal Operations', 'Movie'),
-- Holmes Family
('Mycroft', 'Holmes', 'mholmes', 'mycroft.holmes@britishgov.uk', 'Diogenes Club, London, England', '+44-20-7946-0012', '+44-77-5550-0012', 'British Government', 'Government Official', 'Intelligence', 'Movie'),
-- Baker Street Irregulars
('Wiggins', 'of Baker Street', 'wiggins', 'wiggins@irregulars.uk', 'Baker Street, London, England', '+44-20-7946-0013', '+44-77-5550-0013', 'Baker Street Irregulars', 'Leader of Street Urchins', 'Intelligence Network', 'Movie','Last name created for compatibility'),
-- Supporting Characters
('Mary', 'Morstan', 'mmorstan', 'mary.morstan@watson.uk', '221B Baker Street, London, England', '+44-20-7946-0014', '+44-77-5550-0014', 'Watson Household', 'Mrs. Watson', 'Family', 'Movie'),
('Henry', 'Baskerville', 'hbaskerville', 'henry.baskerville@baskerville.uk', 'Baskerville Hall, Devonshire, England', '+44-20-7946-0015', '+44-77-5550-0015', 'Baskerville Estate', 'Baronet', 'Aristocracy', 'Movie'),
('Dr.', 'Mortimer', 'dmortimer', 'mortimer@devonshire.uk', 'Devonshire, England', '+44-20-7946-0016', '+44-77-5550-0016', 'Private Practice', 'Country Doctor', 'Medical', 'Movie'),
('Stapleton', 'of Devonshire', 'stapleton', 'stapleton@baskerville.uk', 'Merripit House, Devonshire', '+44-20-7946-0017', '+44-77-5550-0017', 'Naturalist', 'Naturalist', 'Science', 'Movie','Last name created for compatibility'),
-- Additional Notable Characters
('James', 'Windibank', 'jwindibank', 'windibank@plumber.uk', 'London, England', '+44-20-7946-0018', '+44-77-5550-0018', 'Westhouse & Marbank', 'Wine Merchant', 'Commerce', 'Movie'),
('Hosmer', 'Angel', 'hangel', 'hosmer.angel@mystery.uk', 'London, England', '+44-20-7946-0019', '+44-77-5550-0019', 'Unknown', 'Mysterious Suitor', 'Unknown', 'Movie'),
('Dr.', 'Grimesby Roylott', 'groylott', 'roylott@stokemoran.uk', 'Stoke Moran, Surrey, England', '+44-20-7946-0020', '+44-77-5550-0020', 'Private Practice', 'Doctor (Retired)', 'Medical (Retired)', 'Movie'),
('Helen', 'Stoner', 'hstoner', 'helen.stoner@stokemoran.uk', 'Stoke Moran, Surrey, England', '+44-20-7946-0021', '+44-77-5550-0021', 'Stoner Family', 'Ward', 'Family', 'Movie'),
('Violet', 'Hunter', 'vhunter', 'violet.hunter@governess.uk', 'Hampshire, England', '+44-20-7946-0022', '+44-77-5550-0022', 'Employment Agency', 'Governess', 'Education', 'Movie'),
('Jephro', 'Rucastle', 'jrucastle', 'jephro.rucastle@copper-beeches.uk', 'The Copper Beeches, Hampshire', '+44-20-7946-0023', '+44-77-5550-0023', 'Rucastle Estate', 'Landowner', 'Property', 'Movie'),
-- Starfleet Academy (2024 Series) - Starring and Co-Starring Characters
-- Main Cadets
('Sam', 'Rutherford-Kirk', 'srutherford', 'sam.rutherford@starfleet.academy', 'Starfleet Academy, San Francisco', '+1-555-8001', '+1-555-9001', 'Starfleet Academy', 'Cadet', 'Academy Student', 'TV'),
('Nyota', 'Uhura-Young', 'nuhura2', 'nyota.uhura@starfleet.academy', 'Starfleet Academy, San Francisco', '+1-555-8002', '+1-555-9002', 'Starfleet Academy', 'Cadet', 'Academy Student', 'TV'),
('Kerovan', 'Tal', 'kerovan', 'kerovan@starfleet.academy', 'Starfleet Academy, San Francisco', '+1-555-8003', '+1-555-9003', 'Starfleet Academy', 'Cadet', 'Academy Student', 'TV','Last name created for compatibility'),
-- Faculty & Command
('Nona', 'Surik', 'nona', 'nona@starfleet.academy', 'Starfleet Academy, San Francisco', '+1-555-8004', '+1-555-9004', 'Starfleet Academy', 'Commander', 'Academy Leadership', 'TV','Last name created for compatibility'),
('Sulu', 'Hikaru', 'hsulu2', 'hikaru.sulu@starfleet.academy', 'Starfleet Academy, San Francisco', '+1-555-8005', '+1-555-9005', 'Starfleet Academy', 'Chancellor', 'Academy Leadership', 'TV'),
-- Supporting Characters
('Tilly', 'Sylvia', 'stilly2', 'sylvia.tilly@starfleet.academy', 'Starfleet Academy, San Francisco', '+1-555-8006', '+1-555-9006', 'Starfleet Academy', 'Lieutenant', 'Academy Faculty', 'TV'),
-- The Mandalorian - Starring and Co-Starring Characters
-- Main Protagonist
('Din', 'Djarin', 'djarin', 'din.djarin@mandalorian.net', 'Nevarro / Traveling', '+1-555-9001', '+1-555-9101', 'Mandalorian Creed', 'Bounty Hunter', 'Independent Operations', 'TV'),
('Grogu', 'of Yoda''s Species', 'grogu', 'grogu@jedi.temple', 'Traveling with Din Djarin', '+1-555-9002', '+1-555-9102', 'Jedi Order', 'Foundling', 'Force Training', 'TV','Last name created for compatibility'),
-- Main Allies
('Greef', 'Karga', 'gkarga', 'greef.karga@bounty-guild.net', 'Nevarro', '+1-555-9003', '+1-555-9103', 'Bounty Hunters Guild', 'Guild Leader / Magistrate', 'Leadership', 'TV'),
('Cara', 'Dune', 'cdune', 'cara.dune@newrepublic.gov', 'Nevarro', '+1-555-9004', '+1-555-9104', 'New Republic', 'Marshal', 'Law Enforcement', 'TV'),
('Bo-Katan', 'Kryze', 'bkryze', 'bokatan@mandalore.net', 'Mandalore', '+1-555-9005', '+1-555-9105', 'Mandalorians', 'Leader', 'Military Leadership', 'TV'),
-- Major Recurring Characters
('Fennec', 'Shand', 'fshand', 'fennec.shand@assassin.net', 'Tatooine', '+1-555-9006', '+1-555-9106', 'Independent', 'Assassin / Mercenary', 'Operations', 'TV'),
('Boba', 'Fett', 'bfett', 'boba.fett@bounty-hunter.net', 'Tatooine', '+1-555-9007', '+1-555-9107', 'Independent', 'Bounty Hunter / Daimyo', 'Leadership', 'TV'),
('Ahsoka', 'Tano', 'atano', 'ahsoka.tano@jedi.temple', 'Corvus / Traveling', '+1-555-9008', '+1-555-9108', 'Former Jedi Order', 'Jedi Knight', 'Force Operations', 'TV'),
('Peli', 'Motto', 'pmotto', 'peli.motto@hangar.tat', 'Mos Eisley, Tatooine', '+1-555-9009', '+1-555-9109', 'Peli''s Hangar', 'Mechanic', 'Repair Services', 'TV'),
-- Supporting Characters
('IG', '11', 'ig11', 'ig11@droid.net', 'Nevarro', '+1-555-9010', '+1-555-9110', 'Independent Droid', 'Nurse Droid', 'Medical / Protection', 'TV'),
('Kuiil', 'the Ugnaught', 'kuiil', 'kuiil@arvala.net', 'Arvala-7', '+1-555-9011', '+1-555-9111', 'Independent', 'Ugnaught Farmer', 'Agriculture', 'TV','Last name created for compatibility'),
('The', 'Armorer', 'armorer', 'armorer@mandalorian.net', 'Mandalorian Covert', '+1-555-9012', '+1-555-9112', 'Mandalorian Creed', 'Armorer', 'Weapons & Armor', 'TV'),
('Paz', 'Vizsla', 'pvizsla', 'paz.vizsla@mandalorian.net', 'Mandalorian Covert', '+1-555-9013', '+1-555-9113', 'Mandalorian Creed', 'Heavy Infantry', 'Military', 'TV'),
-- Antagonists
('Moff', 'Gideon', 'mgideon', 'gideon@imperialremnant.net', 'Imperial Remnant', '+1-555-9014', '+1-555-9114', 'Imperial Remnant', 'Moff', 'Military Command', 'TV'),
('Migs', 'Mayfeld', 'mmayfeld', 'mayfeld@mercenary.net', 'Traveling', '+1-555-9015', '+1-555-9115', 'Independent', 'Ex-Imperial Sharpshooter', 'Mercenary Work', 'TV'),
-- Additional Allies
('Cobb', 'Vanth', 'cvanth', 'cobb.vanth@freetown.tat', 'Mos Pelgo / Freetown, Tatooine', '+1-555-9016', '+1-555-9116', 'Freetown', 'Marshal', 'Law Enforcement', 'TV'),
-- Doctor Strange characters (MCU)
('Stephen', 'Strange', 'sstrange', 'stephen.strange@sanctum.mcu', '177A Bleecker Street, New York, NY', '+1-212-555-0101', '+1-212-555-1101', 'Masters of the Mystic Arts', 'Sorcerer Supreme', 'Mystic Arts', 'Movie'),
('Wong', 'of Kamar-Taj', 'wong', 'wong@kamartaj.mcu', 'Kamar-Taj, Nepal', '+1-212-555-0102', '+1-212-555-1102', 'Masters of the Mystic Arts', 'Sorcerer Supreme', 'Mystic Arts', 'Movie','Last name created for compatibility'),
('Ancient One', 'the Timeless', 'ancientone', 'ancient.one@kamartaj.mcu', 'Kamar-Taj, Nepal', '+1-212-555-0103', '+1-212-555-1103', 'Masters of the Mystic Arts', 'Sorcerer Supreme (Former)', 'Mystic Arts', 'Movie','Last name created for compatibility'),
('Karl', 'Mordo', 'kmordo', 'karl.mordo@kamartaj.mcu', 'Kamar-Taj, Nepal', '+1-212-555-0104', '+1-212-555-1104', 'Masters of the Mystic Arts', 'Master Sorcerer', 'Mystic Arts', 'Movie'),
('Christine', 'Palmer', 'cpalmer', 'christine.palmer@hospital.mcu', 'Metro-General Hospital, New York, NY', '+1-212-555-0105', '+1-212-555-1105', 'Metro-General Hospital', 'Surgeon', 'Emergency Medicine', 'Movie'),
('Kaecilius', 'the Zealot', 'kaecilius', 'kaecilius@zealots.mcu', 'Dark Dimension', '+1-212-555-0106', '+1-212-555-1106', 'Zealots', 'Dark Sorcerer', 'Dark Arts', 'Movie','Last name created for compatibility'),
('America', 'Chavez', 'achavez', 'america.chavez@multiverse.mcu', 'Multiverse', '+1-212-555-0107', '+1-212-555-1107', 'Independent', 'Multiverse Traveler', 'Dimensional Travel', 'Movie'),
-- Thor characters (MCU)
('Thor', 'Odinson', 'thorodinson', 'thor@asgard.mcu', 'New Asgard, Norway', '+47-555-0201', '+47-555-1201', 'Asgard', 'God of Thunder', 'Royal Family', 'Movie'),
('Loki', 'Laufeyson', 'loki', 'loki@asgard.mcu', 'Asgard / Jotunheim', '+47-555-0202', '+47-555-1202', 'Asgard', 'God of Mischief', 'Royal Family', 'Movie'),
('Odin', 'Borson', 'odin', 'odin@asgard.mcu', 'Asgard', '+47-555-0203', '+47-555-1203', 'Asgard', 'All-Father', 'Royal Family', 'Movie'),
('Frigga', 'Odinsdottir', 'frigga', 'frigga@asgard.mcu', 'Asgard', '+47-555-0204', '+47-555-1204', 'Asgard', 'Queen of Asgard', 'Royal Family', 'Movie','Last name created for compatibility'),
('Heimdall', 'the Gatekeeper', 'heimdall', 'heimdall@asgard.mcu', 'Bifrost, Asgard', '+47-555-0205', '+47-555-1205', 'Asgard', 'Guardian of the Bifrost', 'Security', 'Movie','Last name created for compatibility'),
('Sif', 'the Warrior', 'sif', 'sif@asgard.mcu', 'Asgard', '+47-555-0206', '+47-555-1206', 'Asgard', 'Warrior', 'Military', 'Movie','Last name created for compatibility'),
('Valkyrie', 'of Asgard', 'valkyrie', 'valkyrie@asgard.mcu', 'New Asgard, Norway', '+47-555-0207', '+47-555-1207', 'Asgard', 'King of New Asgard', 'Leadership', 'Movie','Last name created for compatibility'),
('Hela', 'Odinsdottir', 'hela', 'hela@asgard.mcu', 'Hel', '+47-555-0208', '+47-555-1208', 'Asgard', 'Goddess of Death', 'Conquest', 'Movie'),
('Jane', 'Foster', 'jfoster', 'jane.foster@astrophysics.mcu', 'New Mexico', '+1-505-555-0209', '+1-505-555-1209', 'Independent Researcher', 'Astrophysicist', 'Science', 'Movie'),
('Erik', 'Selvig', 'eselvig', 'erik.selvig@science.mcu', 'New Mexico', '+1-505-555-0210', '+1-505-555-1210', 'Independent Researcher', 'Astrophysicist', 'Science', 'Movie'),
('Darcy', 'Lewis', 'dlewis', 'darcy.lewis@science.mcu', 'New Mexico', '+1-505-555-0211', '+1-505-555-1211', 'Independent Researcher', 'Astrophysicist', 'Science', 'Movie'),
-- Iron Man characters (MCU)
('Tony', 'Stark', 'tstark', 'tony.stark@starkindustries.mcu', 'Stark Tower, New York, NY', '+1-212-555-0301', '+1-212-555-1301', 'Stark Industries', 'CEO / Iron Man', 'Executive Leadership', 'Movie'),
('Pepper', 'Potts', 'ppotts', 'pepper.potts@starkindustries.mcu', 'Stark Tower, New York, NY', '+1-212-555-0302', '+1-212-555-1302', 'Stark Industries', 'CEO', 'Executive Leadership', 'Movie'),
('James', 'Rhodes', 'jrhodes', 'james.rhodes@airforce.mcu', 'Edwards Air Force Base, CA', '+1-661-555-0303', '+1-661-555-1303', 'US Air Force', 'Colonel / War Machine', 'Military', 'Movie'),
('Obadiah', 'Stane', 'ostane', 'obadiah.stane@starkindustries.mcu', 'Stark Industries, CA', '+1-310-555-0304', '+1-310-555-1304', 'Stark Industries', 'Executive (Former)', 'Executive Leadership', 'Movie'),
('Happy', 'Hogan', 'hhogan', 'happy.hogan@starkindustries.mcu', 'Stark Tower, New York, NY', '+1-212-555-0305', '+1-212-555-1305', 'Stark Industries', 'Head of Security', 'Security', 'Movie'),
('Justin', 'Hammer', 'jhammer', 'justin.hammer@hammertech.mcu', 'Hammer Industries, NY', '+1-212-555-0306', '+1-212-555-1306', 'Hammer Industries', 'CEO', 'Executive Leadership', 'Movie'),
('Ivan', 'Vanko', 'ivanko', 'ivan.vanko@independent.mcu', 'Monaco / Russia', '+33-555-0307', '+33-555-1307', 'Independent', 'Weapons Designer', 'Engineering', 'Movie'),
('Howard', 'Stark', 'hstark', 'howard.stark@starkindustries.mcu', 'Stark Industries, NY', '+1-212-555-0309', '+1-212-555-1309', 'Stark Industries', 'Founder / Scientist', 'Research & Development', 'Movie'),
-- Ant-Man characters (MCU)
('Scott', 'Lang', 'slang', 'scott.lang@antman.mcu', 'San Francisco, CA', '+1-415-555-0401', '+1-415-555-1401', 'X-Con Security', 'Ant-Man', 'Security', 'Movie'),
('Hope', 'van Dyne', 'hvandyne', 'hope.vandyne@pymtech.mcu', 'San Francisco, CA', '+1-415-555-0402', '+1-415-555-1402', 'Pym Technologies', 'CEO / The Wasp', 'Executive Leadership', 'Movie'),
('Hank', 'Pym', 'hpym', 'hank.pym@pymtech.mcu', 'San Francisco, CA', '+1-415-555-0403', '+1-415-555-1403', 'Pym Technologies', 'Founder / Scientist', 'Research & Development', 'Movie'),
('Janet', 'van Dyne', 'jvandyne', 'janet.vandyne@pymtech.mcu', 'Quantum Realm / San Francisco', '+1-415-555-0404', '+1-415-555-1404', 'Pym Technologies', 'The Wasp (Original)', 'Science', 'Movie'),
('Cassie', 'Lang', 'clang', 'cassie.lang@home.mcu', 'San Francisco, CA', '+1-415-555-0405', '+1-415-555-1405', 'Student', 'Student', 'Education', 'Movie'),
('Luis', 'Garcia', 'lgarcia', 'luis.garcia@xcon.mcu', 'San Francisco, CA', '+1-415-555-0406', '+1-415-555-1406', 'X-Con Security', 'Security Consultant', 'Security', 'Movie','Last name created for compatibility'),
('Dave', 'Chen', 'dchen', 'dave.chen@xcon.mcu', 'San Francisco, CA', '+1-415-555-0407', '+1-415-555-1407', 'X-Con Security', 'Security Consultant', 'Security', 'Movie','Last name created for compatibility'),
('Kurt', 'Goreshter', 'kgoreshter', 'kurt.goreshter@xcon.mcu', 'San Francisco, CA', '+1-415-555-0408', '+1-415-555-1408', 'X-Con Security', 'Security Consultant', 'Security', 'Movie','Last name created for compatibility'),
('Darren', 'Cross', 'dcross', 'darren.cross@pymtech.mcu', 'Pym Technologies, CA', '+1-415-555-0409', '+1-415-555-1409', 'Pym Technologies', 'CEO (Former)', 'Executive Leadership', 'Movie'),
('Bill', 'Foster', 'bfoster', 'bill.foster@goliath.mcu', 'Los Angeles, CA', '+1-310-555-0410', '+1-310-555-1410', 'S.H.I.E.L.D. (Former)', 'Scientist / Goliath', 'Science', 'Movie');
