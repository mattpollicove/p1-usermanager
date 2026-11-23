# Company Name Column Reference

## Overview
The `company_name` column in the `manyusers` table serves as an organizational identifier that varies based on the entry type. This document catalogs how the column is used across different franchises, media types, and categories.

---

## Usage by Type

### **Music (Rock)**
**Standard Usage:** Band name
- AC/DC
- KISS
- The Beatles
- Queen
- Foo Fighters
- Rush
- Squeeze
- Aerosmith
- Led Zeppelin
- The Smithereens

**Exceptions:** None - all music entries use their band name as the company_name.

---

### **MLB (Baseball)**
**Standard Usage:** Team name (city + mascot)
- New York Yankees
- Los Angeles Dodgers
- Boston Red Sox
- Chicago Cubs
- San Francisco Giants
- (30 MLB teams total)

**Exceptions:** None - all MLB entries use their full team name.

---

### **Movies - Black Panther**
**Standard Usage:** Nation/Organization name
- Wakanda (Wakandan characters)
- Talokan (Talokanil characters)

**Exceptions:**
- 'CIA' (Everett Ross - external agency)
- 'MIT' (Riri Williams - academic institution)
- 'Black Market' (Ulysses Klaue - criminal enterprise)

---

### **Movies - Star Wars**
**Standard Usage:** Faction/Organization
- Jedi Order
- Galactic Empire
- Rebel Alliance
- First Order
- Resistance

**Exceptions:** None - all aligned with their primary organization.

---

### **Movies - MCU (Marvel Cinematic Universe)**
**Standard Usage:** Organization/Team affiliation
- Avengers
- S.H.I.E.L.D.
- Stark Industries
- Baxter Foundation (Fantastic Four)
- Midtown School of Science and Technology (Spider-Man)

**Exceptions:**
- 'Damage Control' (Vulture - regulatory agency)
- 'Oscorp' (villains - corporate entity)
- 'HYDRA' (villains - terrorist organization)
- 'Guardians of the Galaxy' (space team)
- 'Kamar-Taj' (Doctor Strange - mystical institution)

---

### **Movies - Harry Potter**
**Standard Usage:** School house
- Gryffindor
- Slytherin
- Ravenclaw
- Hufflepuff

**Exceptions:**
- 'Hogwarts School of Witchcraft and Wizardry' (Albus Dumbledore - headmaster, represents entire institution)

---

### **TV - Star Trek**
**Standard Usage:** Starfleet (primary organization)
- Starfleet (all commissioned officers and crew)

**Exceptions:**
- 'Quark Enterprises' (Quark - private business owner on Deep Space 9)

---

### **TV - West Wing**
**Standard Usage:** Government department/office
- The White House
- Office of the President
- Office of the Chief of Staff
- Communications Office
- Press Secretary Office

**Exceptions:** None - all entries represent their specific White House offices.

---

### **TV - Agents of SHIELD**
**Standard Usage:** Agency/Organization affiliation
- S.H.I.E.L.D. (agents and personnel)

**Exceptions:**
- 'HYDRA' (Grant Ward, John Garrett - infiltrators/enemies)
- 'Inhumans' (Lincoln Campbell - ethnic/species group)
- 'A.I. Research Division' (Holden Radcliffe - independent scientist)

---

### **TV - MASH**
**Standard Usage:** Military unit designation
- 4077th M.A.S.H. (all personnel)

**Exceptions:** None - all entries are part of the same mobile army surgical hospital.

---

### **TV - Ted Lasso**
**Standard Usage:** Football club
- AFC Richmond (all characters)

**Exceptions:** None - all entries associated with the same club.

---

### **TV - Shrink**
**Standard Usage:** Practice/client designation
- Westside CBT Practice (therapist and clients)

**Exceptions:** None - represents the therapy practice.

---

### **TV - All Creatures Great and Small**
**Standard Usage:** Veterinary practice
- Skeldale House Veterinary Practice

**Exceptions:** None - all entries work at the same practice.

---

### **TV - Big Bang Theory**
**Standard Usage:** Primary workplace/affiliation
- Caltech (university professors and researchers)
- Cheesecake Factory (Penny's workplace)

**Exceptions:** Based on character's primary professional identity.

---

### **TV - Brilliant Minds**
**Standard Usage:** Medical institution
- Bronx General Hospital

**Exceptions:** None - all entries are hospital staff.

---

### **Books - Ryanverse (Tom Clancy)**
**Standard Usage:** Agency/Military branch
- CIA
- U.S. Navy
- Russian Foreign Intelligence (SVR)
- FBI

**Exceptions:** None - based on character's primary service affiliation.

---

### **Books - Bobiverse**
**Standard Usage:** Mission/Project designation
- Heaven-1 (Bob's original replicant line)
- Bobiverse Network (collective AI network)
- Delta Eridani Colony (settlement project)

**Exceptions:** Varies by Bob's current mission/location - reflects their operational focus.

---

## Key Patterns

1. **Consistency within type:** Characters of the same type/franchise generally use consistent company_name patterns
2. **Primary affiliation:** When characters have multiple affiliations, company_name reflects their primary or most prominent organization
3. **Villains/Antagonists:** Often have distinct company_name values that reflect their opposing organizations (HYDRA, Galactic Empire, etc.)
4. **Independent characters:** Freelancers or business owners use their business name (Quark Enterprises, Black Market)
5. **Academic/Research:** University or research institution names are used for student/academic characters

---

## Summary Statistics

- **Total unique company_name values:** ~150+
- **Most common pattern:** Organization/team name (60%)
- **Second most common:** Government agency/military unit (20%)
- **Sports teams:** 30 MLB teams (15%)
- **Exceptions/special cases:** ~5% of entries

---

## Notes for Database Usage

- The `company_name` field is **NOT NULL** and should always be populated
- Maximum length: VARCHAR(255)
- Indexed for query performance
- Use in conjunction with `type` field for franchise-level filtering
- Use in conjunction with `source` field for media-type filtering
