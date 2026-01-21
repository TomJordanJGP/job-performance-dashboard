/**
 * Google Apps Script to monitor and manage BigQuery Extracted Data
 *
 * Since BigQuery DATASOURCE sheets cannot be read programmatically,
 * this script works with EXTRACTED data instead.
 *
 * Workflow:
 * 1. Manually click "Extract" button in BigQuery toolbar (or set up scheduled extract in BigQuery)
 * 2. Google Sheets creates an "Extract of [sheet name]" sheet
 * 3. This script monitors for that extract and copies it to a stable sheet name
 * 4. Dashboard reads from the stable sheet name
 *
 * Setup Instructions:
 * 1. Open your Google Sheet
 * 2. Click on the BigQuery sheet tab
 * 3. Click "Extract" button in the BigQuery toolbar
 * 4. An "Extract of job-performance-details_combined_2" sheet will be created
 * 5. Install this script (Extensions > Apps Script)
 * 6. Run setupMonitor() function
 */

// Configuration
const CONFIG = {
  // Pattern to match extract sheets (Google Sheets creates these when you click Extract)
  EXTRACT_PATTERN: /^Extract of (.+)$/,

  // The specific extract we're looking for
  SOURCE_EXTRACT_NAME: 'Extract of job-performance-details_combined_2',

  // Stable destination sheet name for the dashboard
  DEST_SHEET_NAME: 'job_data_copy',

  // Backup configuration
  KEEP_HISTORY: true,
  MAX_HISTORY: 5,

  // How often to check for new extracts (in minutes)
  CHECK_INTERVAL_MINUTES: 30
};

/**
 * Main function - checks for extract and copies to stable sheet
 */
function processExtract() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  try {
    Logger.log('Checking for extract...');

    // Look for the extract sheet
    const extractSheet = ss.getSheetByName(CONFIG.SOURCE_EXTRACT_NAME);

    if (!extractSheet) {
      Logger.log(`No extract found: ${CONFIG.SOURCE_EXTRACT_NAME}`);
      Logger.log('Remember to click "Extract" in the BigQuery toolbar first!');
      return {
        success: false,
        message: 'Extract sheet not found'
      };
    }

    Logger.log('Extract sheet found!');

    // Get all data from extract
    const extractRange = extractSheet.getDataRange();
    const extractData = extractRange.getValues();

    if (extractData.length === 0) {
      Logger.log('Warning: Extract sheet is empty');
      return {
        success: false,
        message: 'Extract is empty'
      };
    }

    Logger.log(`Found ${extractData.length} rows in extract`);

    // Create or get destination sheet
    let destSheet = ss.getSheetByName(CONFIG.DEST_SHEET_NAME);

    if (!destSheet) {
      Logger.log(`Creating new sheet: ${CONFIG.DEST_SHEET_NAME}`);
      destSheet = ss.insertSheet(CONFIG.DEST_SHEET_NAME);
    } else {
      // Clear existing data
      destSheet.clear();
    }

    // Copy data to destination
    const destRange = destSheet.getRange(1, 1, extractData.length, extractData[0].length);
    destRange.setValues(extractData);

    // Copy formatting
    const extractFormats = extractRange.getNumberFormats();
    destRange.setNumberFormats(extractFormats);

    // Freeze header row
    destSheet.setFrozenRows(1);

    // Add timestamp
    const timestamp = new Date();
    destSheet.getRange('A1').setNote(`Last updated: ${timestamp.toLocaleString()}\nSource: ${CONFIG.SOURCE_EXTRACT_NAME}`);

    Logger.log(`Successfully copied data to ${CONFIG.DEST_SHEET_NAME}`);
    Logger.log(`Timestamp: ${timestamp.toLocaleString()}`);

    // Create backup if enabled
    if (CONFIG.KEEP_HISTORY) {
      createBackup(extractData, timestamp);
    }

    // Archive the extract sheet (rename it)
    archiveExtract(extractSheet, timestamp);

    return {
      success: true,
      rows: extractData.length,
      timestamp: timestamp
    };

  } catch (error) {
    Logger.log(`Error: ${error.message}`);
    Logger.log(error.stack);
    throw error;
  }
}

/**
 * Archive the extract sheet by renaming it with timestamp
 */
function archiveExtract(extractSheet, timestamp) {
  try {
    const dateStr = Utilities.formatDate(timestamp, Session.getScriptTimeZone(), 'yyyy-MM-dd_HHmm');
    const archiveName = `Extract_Archive_${dateStr}`;
    extractSheet.setName(archiveName);
    Logger.log(`Archived extract as: ${archiveName}`);

    // Clean up old archives
    cleanupOldArchives();
  } catch (error) {
    Logger.log(`Warning: Could not archive extract: ${error.message}`);
  }
}

/**
 * Create a timestamped backup copy
 */
function createBackup(data, timestamp) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const dateStr = Utilities.formatDate(timestamp, Session.getScriptTimeZone(), 'yyyy-MM-dd_HHmm');
    const backupName = `${CONFIG.DEST_SHEET_NAME}_backup_${dateStr}`;

    const backupSheet = ss.insertSheet(backupName);
    const backupRange = backupSheet.getRange(1, 1, data.length, data[0].length);
    backupRange.setValues(data);
    backupSheet.setFrozenRows(1);

    Logger.log(`Created backup: ${backupName}`);
    cleanupOldBackups();
  } catch (error) {
    Logger.log(`Warning: Could not create backup: ${error.message}`);
  }
}

/**
 * Remove old backup sheets
 */
function cleanupOldBackups() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const allSheets = ss.getSheets();

  const backupSheets = allSheets
    .filter(sheet => sheet.getName().startsWith(`${CONFIG.DEST_SHEET_NAME}_backup_`))
    .sort((a, b) => b.getName().localeCompare(a.getName()));

  if (backupSheets.length > CONFIG.MAX_HISTORY) {
    for (let i = CONFIG.MAX_HISTORY; i < backupSheets.length; i++) {
      ss.deleteSheet(backupSheets[i]);
      Logger.log(`Deleted old backup: ${backupSheets[i].getName()}`);
    }
  }
}

/**
 * Remove old archived extracts
 */
function cleanupOldArchives() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const allSheets = ss.getSheets();

  const archiveSheets = allSheets
    .filter(sheet => sheet.getName().startsWith('Extract_Archive_'))
    .sort((a, b) => b.getName().localeCompare(a.getName()));

  // Keep only the 3 most recent archives
  if (archiveSheets.length > 3) {
    for (let i = 3; i < archiveSheets.length; i++) {
      ss.deleteSheet(archiveSheets[i]);
      Logger.log(`Deleted old archive: ${archiveSheets[i].getName()}`);
    }
  }
}

/**
 * Set up trigger to check for extracts every 30 minutes
 */
function setupMonitor() {
  deleteTriggers();

  ScriptApp.newTrigger('processExtract')
    .timeBased()
    .everyMinutes(30)
    .create();

  Logger.log('Monitor set up to check for extracts every 30 minutes');

  // Try to process immediately if extract exists
  try {
    const result = processExtract();
    if (result.success) {
      SpreadsheetApp.getUi().alert(
        'Success!',
        `Processed extract successfully!\n\n` +
        `Copied ${result.rows} rows to "${CONFIG.DEST_SHEET_NAME}"\n\n` +
        `The script will now monitor for new extracts every 30 minutes.\n\n` +
        `Remember to click "Extract" in the BigQuery toolbar when you want to refresh the data.`,
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    } else {
      SpreadsheetApp.getUi().alert(
        'Setup Complete',
        `Monitor is now active!\n\n` +
        `No extract found yet. To get started:\n\n` +
        `1. Click on the BigQuery sheet tab\n` +
        `2. Click "Extract" in the BigQuery toolbar\n` +
        `3. Wait for extract to complete\n` +
        `4. The script will automatically process it\n\n` +
        `Or click "BigQuery Sync > Process Extract" to try again.`,
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    }
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      'Setup Complete',
      `Monitor is active, but no extract found yet.\n\n` +
      `Click "Extract" in the BigQuery toolbar to create one.`,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * Delete all triggers
 */
function deleteTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));
  Logger.log('Deleted all existing triggers');
}

/**
 * Manual process function
 */
function manualProcess() {
  const ui = SpreadsheetApp.getUi();

  try {
    const result = processExtract();
    if (result.success) {
      ui.alert(
        'Success!',
        `Copied ${result.rows} rows to ${CONFIG.DEST_SHEET_NAME}\n` +
        `Timestamp: ${result.timestamp.toLocaleString()}`,
        ui.ButtonSet.OK
      );
    } else {
      ui.alert(
        'No Extract Found',
        `No extract sheet found.\n\n` +
        `To create an extract:\n` +
        `1. Click on the BigQuery sheet tab\n` +
        `2. Click "Extract" in the BigQuery toolbar\n` +
        `3. Wait for it to complete\n` +
        `4. Run this again`,
        ui.ButtonSet.OK
      );
    }
  } catch (error) {
    ui.alert('Error', `Failed to process extract: ${error.message}`, ui.ButtonSet.OK);
  }
}

/**
 * Create custom menu
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('BigQuery Sync')
    .addItem('Process Extract', 'manualProcess')
    .addItem('Setup Auto-Monitor', 'setupMonitor')
    .addItem('Remove Auto-Monitor', 'deleteTriggers')
    .addToUi();
}
