/**
 * Google Apps Script to automatically copy BigQuery connected sheet data
 * to a regular sheet tab that can be accessed via API.
 *
 * Setup Instructions:
 * 1. Open your Google Sheet
 * 2. Go to Extensions > Apps Script
 * 3. Delete any existing code
 * 4. Paste this code
 * 5. Click the disk icon to save
 * 6. Run the "setupTrigger" function once to set up automatic refresh
 */

// Configuration
const CONFIG = {
  // Source sheet (BigQuery connected sheet)
  SOURCE_SHEET_NAME: 'job-performance-details_combined_2',

  // Destination sheet (regular sheet that API can read)
  DEST_SHEET_NAME: 'job_data_copy',

  // How many backup copies to keep (optional)
  KEEP_HISTORY: true,
  MAX_HISTORY: 3, // Keep last 3 copies

  // Auto-refresh interval (in minutes)
  // BigQuery sheet refreshes every 3-4 hours, so we'll check hourly
  REFRESH_INTERVAL_MINUTES: 60
};

/**
 * Main function to copy data from BigQuery sheet to regular sheet
 */
function copyBigQueryData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  try {
    Logger.log('Starting data copy...');

    // Get source sheet
    const sourceSheet = ss.getSheetByName(CONFIG.SOURCE_SHEET_NAME);
    if (!sourceSheet) {
      throw new Error(`Source sheet "${CONFIG.SOURCE_SHEET_NAME}" not found`);
    }

    // Get all data from source (including headers)
    const sourceRange = sourceSheet.getDataRange();
    const sourceData = sourceRange.getValues();

    if (sourceData.length === 0) {
      Logger.log('Warning: Source sheet is empty');
      return;
    }

    Logger.log(`Found ${sourceData.length} rows in source sheet`);

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
    const destRange = destSheet.getRange(1, 1, sourceData.length, sourceData[0].length);
    destRange.setValues(sourceData);

    // Copy formatting (optional)
    const sourceFormats = sourceRange.getNumberFormats();
    destRange.setNumberFormats(sourceFormats);

    // Freeze header row
    destSheet.setFrozenRows(1);

    // Add timestamp to sheet
    const timestamp = new Date();
    destSheet.getRange('A1').setNote(`Last updated: ${timestamp.toLocaleString()}`);

    Logger.log(`Successfully copied data to ${CONFIG.DEST_SHEET_NAME}`);
    Logger.log(`Timestamp: ${timestamp.toLocaleString()}`);

    // Create backup if enabled
    if (CONFIG.KEEP_HISTORY) {
      createBackup(sourceData, timestamp);
    }

    return {
      success: true,
      rows: sourceData.length,
      timestamp: timestamp
    };

  } catch (error) {
    Logger.log(`Error: ${error.message}`);
    Logger.log(error.stack);

    // Send email notification on error (optional)
    // sendErrorNotification(error);

    throw error;
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

    // Create backup sheet
    const backupSheet = ss.insertSheet(backupName);
    const backupRange = backupSheet.getRange(1, 1, data.length, data[0].length);
    backupRange.setValues(data);
    backupSheet.setFrozenRows(1);

    Logger.log(`Created backup: ${backupName}`);

    // Clean up old backups
    cleanupOldBackups();

  } catch (error) {
    Logger.log(`Warning: Could not create backup: ${error.message}`);
  }
}

/**
 * Remove old backup sheets, keeping only the most recent ones
 */
function cleanupOldBackups() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const allSheets = ss.getSheets();

  // Find all backup sheets
  const backupSheets = allSheets
    .filter(sheet => sheet.getName().startsWith(`${CONFIG.DEST_SHEET_NAME}_backup_`))
    .sort((a, b) => b.getName().localeCompare(a.getName())); // Sort by name (newest first)

  // Delete old backups beyond the limit
  if (backupSheets.length > CONFIG.MAX_HISTORY) {
    Logger.log(`Found ${backupSheets.length} backups, keeping ${CONFIG.MAX_HISTORY}`);

    for (let i = CONFIG.MAX_HISTORY; i < backupSheets.length; i++) {
      const sheetToDelete = backupSheets[i];
      Logger.log(`Deleting old backup: ${sheetToDelete.getName()}`);
      ss.deleteSheet(sheetToDelete);
    }
  }
}

/**
 * Set up automatic trigger to run every hour
 * Run this function once manually to set up the trigger
 */
function setupTrigger() {
  // Delete existing triggers first
  deleteTriggers();

  // Create new time-based trigger
  ScriptApp.newTrigger('copyBigQueryData')
    .timeBased()
    .everyHours(1)
    .create();

  Logger.log('Trigger set up successfully to run every hour');

  // Run once immediately
  copyBigQueryData();

  SpreadsheetApp.getUi().alert(
    'Success!',
    'Automatic data sync is now set up.\n\n' +
    'The BigQuery data will be copied to "' + CONFIG.DEST_SHEET_NAME + '" every hour.\n\n' +
    'You can now use this sheet with the dashboard API.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

/**
 * Delete all existing triggers for this script
 */
function deleteTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
  Logger.log('Deleted all existing triggers');
}

/**
 * Manual refresh function (adds menu item)
 */
function manualRefresh() {
  const ui = SpreadsheetApp.getUi();

  const result = ui.alert(
    'Manual Refresh',
    'Copy data from BigQuery sheet to ' + CONFIG.DEST_SHEET_NAME + '?',
    ui.ButtonSet.YES_NO
  );

  if (result === ui.Button.YES) {
    try {
      const info = copyBigQueryData();
      ui.alert(
        'Success!',
        `Copied ${info.rows} rows to ${CONFIG.DEST_SHEET_NAME}\n` +
        `Timestamp: ${info.timestamp.toLocaleString()}`,
        ui.ButtonSet.OK
      );
    } catch (error) {
      ui.alert(
        'Error',
        `Failed to copy data: ${error.message}`,
        ui.ButtonSet.OK
      );
    }
  }
}

/**
 * Create custom menu when spreadsheet opens
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('BigQuery Sync')
    .addItem('Manual Refresh', 'manualRefresh')
    .addItem('Setup Auto-Sync', 'setupTrigger')
    .addItem('Remove Auto-Sync', 'deleteTriggers')
    .addToUi();
}

/**
 * Optional: Send email notification on errors
 */
function sendErrorNotification(error) {
  const email = Session.getActiveUser().getEmail();
  const subject = 'BigQuery Data Copy Error';
  const body = `
    Error copying BigQuery data:

    Message: ${error.message}

    Stack: ${error.stack}

    Time: ${new Date().toLocaleString()}
  `;

  MailApp.sendEmail(email, subject, body);
}
