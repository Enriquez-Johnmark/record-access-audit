-- How a patient logs in to see who in the clinic looked at their record.
alter table patients add column email text;
create unique index patients_email on patients (lower(email));
