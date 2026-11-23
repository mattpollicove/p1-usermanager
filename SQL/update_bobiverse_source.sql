-- Update Bobiverse entries to have source = 'Books'
UPDATE userdata.manyusers 
SET source = 'Books' 
WHERE type = 'Bobiverse';
