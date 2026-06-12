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

## Session: 2026-06-11

- **[2026-06-11]** "update requirements, all documention"
- **[2026-06-11]** "from my end what do I need to do on the file system to be ready for mssql connections. e.g., install the jar files (specifiy version and location)"
- **[2026-06-11]** "yes"
- **[2026-06-11]** "yes"
- **[2026-06-11]** "yes, also update documentation with file and url information"
- **[2026-06-11]** "yes, also for oracle and mysql"
- **[2026-06-11]** "commit and push"
- **[2026-06-11]** "when changing profiles I still need to log into keychain twice"
- **[2026-06-11]** "p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 13.0px '.SF NS'; color: #000000; color: rgba(0, 0, 0, 0.85)} p.p2 {margin: 0.0px 0.0px 0.0px 0.0px; font: 13.0px '.SF NS'; color: #000000; color: rgba(0, 0, 0, 0.85); min-height: 16.0px} **Failed to connect to database.** **** **Error details:** **Class com.microsoft.sqlserver.jdbc.SQLServerDriver is not found**"
- **[2026-06-11]** "I am using the recommended path /Users/matthewpollicove/Documents/Projects/p1-usermanager/drivers/mssql/mssql-jdbc-13.4.0.jre11.jar"
- **[2026-06-11]** "**com.microsoft.sqlserver.jdbc.SQLServerException: \"encrypt\" property is set to \"true\" and \"trustServerCertificate\" property is set to \"true\" but the driver could not establish a secure connection to SQL Server by using Secure Sockets Layer (SSL) encryption: Error: (unexpected_message) SQL Server did not return a response. The connection has been closed. ClientConnectionId:54bed01d-08fa-4cca-9c32-2c71170bad5a.**"
- **[2026-06-11]** "**com.microsoft.sqlserver.jdbc.SQLServerException: \"encrypt\" property is set to \"true\" and \"trustServerCertificate\" property is set to \"true\" but the driver could not establish a secure connection to SQL Server by using Secure Sockets Layer (SSL) encryption: Error: (unexpected_message) SQL Server did not return a response. The connection has been closed. ClientConnectionId:1bde2dd4-d43e-4049-8db0-cf905243ee33.**"
