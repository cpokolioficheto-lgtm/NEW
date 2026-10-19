/**
 * Оценки → Memberstack метаданни (Строителен техник)
 *
 * Чете листа „Финални Резултати“ (колони G:Y) и за всеки тест с резултат
 * 60 или повече записва „X / 100“ в метаданните на курсиста в Memberstack.
 * - Не пипа стойност, която вече е по-висока или въведена ръчно с текст.
 * - Резултати под 60 не се записват.
 *
 * Настройка:
 *  1. Project Settings → Script properties → добавете MS_KEY = секретния ключ (sk_...).
 *  2. Пуснете probenRun() – само показва в Execution log какво би записал.
 *  3. Пуснете setup() – включва автоматичната проверка на всеки 15 минути.
 */

var SHEET = 'Финални Резултати';
var FIRST_ROW = 15;  // редовете преди 15 са по стария стандарт
var EMAIL_COL = 7;   // G
// Колони H..Y → ключ в метаданните на Memberstack
var KEYS = [
  'st_zbut', 'st_ikonomika', 'st_pokrivi', 'st_podgotovka', 'st_prtd',
  'st_organizaciq-smr', 'st_grub-stroej', 'st_osp', 'st_informatika',
  'st_vynshni-dovyrshitelni', 'st_vytreshni-dovyrshitelni', 'st_ueisd',
  'st_trd', 'st_ims', 'st_ee', 'st_gi', 'st_zemni-raboti', 'st_organizaciq-rp'
];
var PASS = 60;
// Курсисти, които скриптът не пипа (стар стандарт / въведени ръчно)
var SKIP = ['kanq.simeonova94@gmail.com', 'stoyanpenev@gmail.com', 'imo.hristov@gmail.com'];
var API = 'https://admin.memberstack.com/members/';

function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'syncGrades') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('syncGrades').timeBased().everyMinutes(15).create();
  Logger.log('Включено: проверка на всеки 15 минути.');
}

function probenRun() { run_(true); }
function syncGrades() { run_(false); }

function run_(dry) {
  var key = PropertiesService.getScriptProperties().getProperty('MS_KEY');
  if (!key) throw new Error('Липсва MS_KEY в Script properties.');
  var cache = PropertiesService.getScriptProperties();
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET);
  var last = sh.getLastRow();
  if (last < FIRST_ROW) return;
  var rows = sh.getRange(FIRST_ROW, EMAIL_COL, last - FIRST_ROW + 1, 1 + KEYS.length).getValues();

  rows.forEach(function (r) {
    var email = String(r[0] || '').trim().toLowerCase();
    if (!email || email.indexOf('@') < 0 || SKIP.indexOf(email) >= 0) return;
    var want = {};
    KEYS.forEach(function (k, i) {
      var v = Number(r[i + 1]);
      if (r[i + 1] !== '' && !isNaN(v) && v >= PASS && v <= 100) want[k] = Math.round(v);
    });
    var sig = JSON.stringify(want);
    if (sig === '{}' || cache.getProperty('c:' + email) === sig) return;

    var member = getMember_(key, email);
    if (!member) { Logger.log('Няма профил в Memberstack: ' + email); return; }
    var meta = member.metaData || {};
    var changes = {};
    Object.keys(want).forEach(function (k) {
      var cur = meta[k];
      var m = String(cur == null ? '' : cur).match(/^\s*(\d+)\s*\/\s*100\s*$/);
      var empty = cur == null || cur === '' || cur === 'Не е налична';
      if (empty || (m && Number(m[1]) < want[k])) changes[k] = want[k] + ' / 100';
    });

    if (Object.keys(changes).length) {
      Logger.log((dry ? '[проба] ' : '') + email + ' → ' + JSON.stringify(changes));
      if (!dry) {
        var merged = {};
        Object.keys(meta).forEach(function (k) { merged[k] = meta[k]; });
        Object.keys(changes).forEach(function (k) { merged[k] = changes[k]; });
        var res = UrlFetchApp.fetch(API + encodeURIComponent(member.id), {
          method: 'patch', contentType: 'application/json',
          headers: { 'X-API-KEY': key }, muteHttpExceptions: true,
          payload: JSON.stringify({ metaData: merged })
        });
        if (res.getResponseCode() >= 300) { Logger.log('Грешка ' + res.getResponseCode() + ': ' + res.getContentText()); return; }
      }
    }
    if (!dry) cache.setProperty('c:' + email, sig);
    Utilities.sleep(300);
  });
}

function getMember_(key, email) {
  var res = UrlFetchApp.fetch(API + encodeURIComponent(email), {
    headers: { 'X-API-KEY': key }, muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) return null;
  return JSON.parse(res.getContentText()).data;
}
