# Prompt Log

All user prompts during a session are recorded here with timestamps.

---

## Session: 2026-04-06

- **[2026-04-06]** "address known problems and make sure they don't happen again, add to the checklist of issues to check"
- **[2026-04-06]** "importing via ldap getting 400 Bad Request INVALID_DATA employeeNumber must be a STRING object / address.postalCode must be a STRING object"
- **[2026-04-06]** "User user.0 ... address.postalCode must be a STRING object ... Include checks to make sure all attributes with numeric elements are treated as non number attributes as appropriate when importing to PingOne"
- **[2026-04-06]** "when exporting entries allow creation of filters based on populated attributes"

## Session: 2026-04-14

- **[2026-04-14]** "in import/export mapping enable middle name, employee type. address, and any custom attributes that have been defined in PingOne"
- **[2026-04-14]** "add explicit UI help text updates documenting these new mapping aliases and fields in the in-app help"
- **[2026-04-14]** "update version to .8, push to github"
- **[2026-04-14]** "review all help within the application. make sure it is up to date. include an about box accessible via the menu, the preferences menu item opens a configuration help screen. move this menu item to help and title it configuration help. move the functionality in the settings menu item to a preferences menu item"
- **[2026-04-14]** "move all the preferences options to a separate preferences dialog invoked from the application menu"
- **[2026-04-14]** "all of the preferences are missing. reinstate the preferences items as a preference menu item."
- **[2026-04-14]** "why does \"python\" appear in the menu bar as opposed to the application name \"PingOne User Manager\""
- **[2026-04-14]** "please do this"
- **[2026-04-14]** "The preferences menu option loads configuration help screen. this is incorrect. rename this option as \"Configuration Help\" and move it to the Help Menu"
- **[2026-04-14]** "I do not want this to open configuration help. This item should be in the help menu only. There should be a dedicated settings window with the items currently under pereferences control."
- **[2026-04-14]** "this is still not working. the preferences menu is completely missing and the preferences menu item is still showing configuration help"

## Session: 2026-04-15

- **[2026-04-15]** "during import and export track transactions per second to PingOne, at the end of the operation display a report that shows average TPS, mean TPS and peak TPS"
- **[2026-04-15]** "add TPS reporting for delete operations"
- **[2026-04-15]** "during delete operations show current entry being deleted in status bar"
- **[2026-04-15]** "development rule: always use plan, ask, execute approach"
- **[2026-04-15]** "Export failed: (pymysql.err.OperationalError) (1054, \"Unknown column '_embedded' in 'INSERT INTO'\") ... [metadata fields error in database export]"
- **[2026-04-15]** "filter for all exports, include option to include/exclude metadata fields"
- **[2026-04-15]** "remember preferences, show the list of metadata fields, give the user the option what to include/exclude"
- **[2026-04-15]** "[Same error again] Export failed: (pymysql.err.OperationalError) (1054, \"Unknown column '_embedded' in 'INSERT INTO'\") ... [after adding metadata filtering UI, database exports still included metadata]"
- **[2026-04-15]** "Export failed: (pymysql.err.OperationalError) (1054, \"Unknown column 'account.canAuthenticate' in 'INSERT INTO'\") ... [dotted column names in SQL INSERT]"
- **[2026-04-15]** "Export failed: (pymysql.err.OperationalError) (1054, \"Unknown column 'lifecycle_status' in 'INSERT INTO'\") ... [missing columns in existing table during export]"
- **[2026-04-15]** "in import/export mapping allow the deletion of multiple mapping rows at once. add a checkbox to automatically remove \"link\" attributes."
- **[2026-04-15]** "only export selected fields to database or ldap"
- **[2026-04-15]** "add tps statistics on export"
