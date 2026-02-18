function main(){
  const ss = SpreadsheetApp.getActive();
  const payload = buildPayload(ss);
  const teams = callSolver(payload);
  writeAssignedTeams(ss, teams.teams);
  ss.setActiveSheet(ss.getSheetByName("Entry_List"));
}

/**
 * Generate teams with a specific seed for reproducible results.
 * Different seeds produce different valid team assignments.
 * @param {number} seed - Random seed (any integer)
 */
function mainWithSeed(seed) {
  const ss = SpreadsheetApp.getActive();
  const payload = buildPayload(ss);
  payload.seed = seed;
  const teams = callSolver(payload);
  writeAssignedTeams(ss, teams.teams);
  ss.setActiveSheet(ss.getSheetByName("Entry_List"));
}

function buildPayload(ss) {

  const sheet = ss.getSheetByName("Entry_List");
  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, 5).getValues();

  const fencers = values.filter(row => row[0] != "").map(row => ({
    name: row[0],
    category: row[1],
    preference: {
      foil: row[2],
      epee: row[3],
      sabre: row[4]
    }
  }));

  return { fencers };
}

function callSolver(payload) {
  const url = "XXXXX";
  const response = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  return(JSON.parse(response.getContentText()));
}

function writeAssignedTeams(ss, teams) {
  const sheetName = "Assigned_Teams_Raw";
  let outSheet = ss.getSheetByName(sheetName);
  if (outSheet) {
    ss.deleteSheet(outSheet);
  }
  outSheet = ss.insertSheet(sheetName);

  // Header
  outSheet.getRange(1, 1, 1, 5).setValues([
    ["Team_Name", "Name", "Category", "Assigned_Weapon", "Preference_Score"]
  ]);

  // --- Flatten & write teams ---
  const outputRows = [];

  teams.forEach((team, idx) => {
    Object.keys(team.members).forEach(weapon => {
      const f = team.members[weapon];
      outputRows.push([
        "Team" + team.team,
        f.name,
        f.category,
        weapon,
        f.preference
      ]);
    });
  });

  outSheet.getRange(2, 1, outputRows.length, 5).setValues(outputRows);
}
