/**
 * InkForge — Рівень 3, крок 5: "Експорт друк-PDF".
 *
 * Окремий скрипт (не частина inkforge_layout.jsx), бо це окрема
 * підтверджувана кнопка на сторінці Launcher-а й окремий крок у
 * ланцюжку 1(перевірити)-2(план)-3(зверстати)-4(ручне доправлення в
 * InDesign)-5(цей скрипт). Див. docs/architecture.md, розділ "Рівень 3".
 *
 * На відміну від inkforge_layout.jsx, цей скрипт НЕ відкриває заново
 * .indd з нуля -- якщо в InDesign вже є відкритий документ (типовий
 * випадок: одразу після кроку 3 і ручного доправлення в кроці 4),
 * використовується саме він (app.activeDocument), щоб не загубити
 * ручні правки верстальниці. `docPath` лишається лише fallback-ом на
 * випадок, якщо InDesign запущено окремо без відкритого документа.
 *
 * Очікує app.scriptArgs (проставляються з launcher/indesign_bridge.py):
 *   - planPath (обов'язково) -- шлях до layout_plan.json (звідти береться
 *     cmyk_profile газети).
 *   - pdfPath (обов'язково) -- куди зберегти готовий PDF.
 *   - docPath (необов'язково) -- fallback, якщо немає відкритого документа.
 *   - presetName (необов'язково) -- назва пресету PDF-експорту в InDesign;
 *     за замовчуванням "[PDF/X-1a:2001]" (вбудований пресет Adobe).
 *
 * Якщо app.scriptArgs не задані (запуск вручну з панелі Scripts) -- скрипт
 * запитає файли через діалоги вибору.
 *
 * **НЕ перевірено на реальному InDesign** -- як і inkforge_layout.jsx, це
 * написано за документованим InDesign Scripting DOM, без доступу до
 * реального InDesign у поточному dev-оточенні. Точні назви властивостей
 * (ColorConversion.convertToDestination, destinationProfile тощо) потрібно
 * підтвердити на машині верстальниці (Edit > Adobe PDF Presets,
 * Edit > Color Settings) перш ніж покладатися на цей крок у production.
 */

#target indesign

// Пресет PDF/X-1a:2001 -- вбудований в Adobe InDesign (квадратні дужки --
// частина його точної назви для scripting API, не косметика).
var DEFAULT_PDF_PRESET = "[PDF/X-1a:2001]";

function readTextFile(file) {
    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();
    return content;
}

function scriptArg(key) {
    try {
        if (app.scriptArgs.isDefined(key)) {
            return app.scriptArgs.get(key);
        }
    } catch (e) {
        // app.scriptArgs недоступний у деяких режимах запуску -- це нормально
    }
    return null;
}

function loadLayoutPlan(planFile) {
    var raw = readTextFile(planFile);
    return JSON.parse(raw);
}

/**
 * Повертає документ для експорту. Якщо в InDesign вже є відкритий
 * документ -- використовує саме його (не чіпаючи ручні правки верстальниці
 * після кроку 4). Інакше -- відкриває docPath (scriptArgs або діалог).
 */
function getTargetDocument() {
    if (app.documents.length > 0) {
        return app.activeDocument;
    }

    var docPathArg = scriptArg("docPath");
    if (docPathArg) {
        return app.open(new File(docPathArg));
    }

    var picked = File.openDialog("Немає відкритого документа -- виберіть .indd для експорту в PDF:");
    if (!picked) {
        throw new Error("Файл не вибрано, і немає відкритого документа.");
    }
    return app.open(picked);
}

function pickPlanFile() {
    var fromArgs = scriptArg("planPath");
    if (fromArgs) {
        return new File(fromArgs);
    }
    var picked = File.openDialog("Виберіть layout_plan.json (звідти береться cmyk_profile):");
    if (!picked) {
        throw new Error("layout_plan.json не вибрано.");
    }
    return picked;
}

function pickPdfOutputFile() {
    var fromArgs = scriptArg("pdfPath");
    if (fromArgs) {
        return new File(fromArgs);
    }
    var picked = File.saveDialog("Куди зберегти друк-PDF?");
    if (!picked) {
        throw new Error("Шлях для збереження PDF не вибрано.");
    }
    return picked;
}

function findPdfPreset(presetName) {
    try {
        var preset = app.pdfExportPresets.itemByName(presetName);
        if (preset.isValid) {
            return preset;
        }
    } catch (e) {
        // ігноруємо -- нижче кидаємо зрозумілу помилку самі
    }
    return null;
}

/**
 * Експортує doc у pdfFile за пресетом presetName. Якщо cmykProfileName
 * заданий -- явно вмикає Convert to Destination з цим ICC-профілем (див.
 * docs/architecture.md, "З'ясовано (26.09.2026)": конвертація RGB->CMYK
 * робиться саме тут, а не на Рівні 1). Повертає масив попереджень
 * (порожній -- якщо все ок).
 */
function exportPrintPdf(doc, pdfFile, presetName, cmykProfileName) {
    var warnings = [];

    var preset = findPdfPreset(presetName);
    if (!preset) {
        throw new Error(
            "Пресет PDF-експорту '" + presetName + "' не знайдено в InDesign на цій машині. " +
            "Перевір точну назву в Edit > Adobe PDF Presets і онови layout_plan.json/профіль газети " +
            "(поле pdf_preset, якщо додане) або передай --preset-name."
        );
    }

    if (cmykProfileName) {
        try {
            app.pdfExportPreferences.colorConversion = ColorConversion.convertToDestination;
            app.pdfExportPreferences.destinationProfile = cmykProfileName;
        } catch (e) {
            warnings.push(
                "Не вдалося встановити CMYK-профіль '" + cmykProfileName + "' для PDF-експорту: " +
                e.message + ". Профіль мусить бути встановлений на цій машині (Edit > Color Settings) " +
                "з точно такою назвою -- інакше експорт піде з дефолтною конвертацією кольору пресету."
            );
        }
    } else {
        warnings.push(
            "cmyk_profile не вказано в профілі газети (layout_plan.json) -- " +
            "PDF-експорт використає дефолтну колірну конвертацію пресету, без явного CMYK-профілю."
        );
    }

    doc.exportFile(ExportFormat.PDF_TYPE, pdfFile, false, preset);
    return warnings;
}

function main() {
    var planFile = pickPlanFile();
    var plan = loadLayoutPlan(planFile);

    var doc = getTargetDocument();
    var pdfFile = pickPdfOutputFile();
    var presetName = scriptArg("presetName") || DEFAULT_PDF_PRESET;

    var warnings = exportPrintPdf(doc, pdfFile, presetName, plan.cmyk_profile);

    for (var i = 0; i < warnings.length; i++) {
        $.writeln("[Рівень 3, експорт PDF] УВАГА -- " + warnings[i]);
    }
    $.writeln(
        "[Рівень 3, експорт PDF] Готово: '" + pdfFile.fsName + "' (пресет '" + presetName + "'); " +
        "перевірка на реальному InDesign ще потрібна."
    );
}

main();
