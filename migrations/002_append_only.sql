-- Flags, cases and rule-set versions are never changed or removed once written.
create trigger flags_no_truncate before truncate on flags
    for each statement execute function refuse_change();
create trigger cases_append_only before update or delete on cases
    for each row execute function refuse_change();
create trigger cases_no_truncate before truncate on cases
    for each statement execute function refuse_change();
create trigger rule_set_versions_append_only before update or delete on rule_set_versions
    for each row execute function refuse_change();
create trigger rule_set_versions_no_truncate before truncate on rule_set_versions
    for each statement execute function refuse_change();
