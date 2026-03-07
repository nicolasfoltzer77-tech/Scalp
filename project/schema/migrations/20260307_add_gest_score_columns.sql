-- Ensure score columns required by DEC→TRIGGERS→GEST propagation exist in gest.
ALTER TABLE gest ADD COLUMN score_C REAL;
ALTER TABLE gest ADD COLUMN score_S REAL;
ALTER TABLE gest ADD COLUMN score_H REAL;
ALTER TABLE gest ADD COLUMN score_M REAL;

ALTER TABLE gest ADD COLUMN score_of REAL;
ALTER TABLE gest ADD COLUMN score_mo REAL;
ALTER TABLE gest ADD COLUMN score_br REAL;
ALTER TABLE gest ADD COLUMN score_force REAL;
