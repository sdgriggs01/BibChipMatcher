# Bib Chip Matcher

## Inputs
- a tags file that is any CSV of chip labels and chip IDs; the default file is `chipLabel_chipID_map.txt`
- the tags CSV includes headers
- a Google spreadsheet with one sheet per team; each sheet lists the team's roster and assigned competitor numbers
- a list of teams participating in the given meet; this may be a subset of the teams present in the spreadsheet
- the distance of the meet, which is required for the HyTek output format

## Outputs
- a HyTek-formatted entries file
- a printable sheet for each team with each team's assignments on a separate page, listing each athlete's competitor number and chip label
- a tags CSV file with headers, where each row maps bib number to chip ID

## Process
- read the chipLabel_chipID_map.txt into a map of chip labels to chip IDs
- download the spreadsheet and read it into a data structure that holds each team's list of athletes, their names, their genders, and competitor numbers
- loop over each team in the meet and assign each athlete a chip ID, noting the label on the chip. Do this by team so each team has a continuous block of chip labels
- output the tag file mapping each bib number to its chip ID
- output the HyTek entry file, using the E record format

## Resources
URL of Team Roster Spreadsheet: https://docs.google.com/spreadsheets/d/1Q8pEsPonUOy5raCcaGxX2Y_NwDcJ8LaXgWDebFgGCnM/edit?gid=1140587109#gid=1140587109

Hytek Format Spec - [Found Here](HytekEntryFormat.html)