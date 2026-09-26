/*
 * InkForge — Рівень 2, виконавець ExtendScript (Adobe InDesign).
 *
 * СТАТУС: частковий, НЕ перевірений на реальному InDesign (у середовищі
 * розробки немає встановленого InDesign). Реалізовано лише те, що не
 * залежить від ще невідомої мапи "Self ID фрейма -> роль статті" для кожної
 * газети (див. розділ "Відкриті питання" у docs/architecture.md):
 *
 *   1. Preflight шрифтів — звірка layout_plan.json (fonts_installed /
 *      fonts_substituted, взяті з профілю газети) з реальним статусом
 *      шрифтів на цій машині через app.fonts.
 *   2. Простановка змінних колонтитула (дата випуску, номер) через
 *      Text Variables документа.
 *
 * ЩЕ НЕ РЕАЛІЗОВАНО (навмисно, не забуто):
 *   - Розчищення старого вмісту фреймів і заповнення новими статтями/фото
 *     за layout_plan.json (relink фото, застосування Horizontal Scale
 *     97-102%). Це вимагає стабільної мапи "який фрейм на сторінці
 *     відповідає якій ролі статті", якої в profiles/*.yaml ще немає —
 *     потрібен окремий прохід аналізу IDML (Self ID кожного фрейма на
 *     кожному розвороті) перш ніж тут можна писати реальний relink.
 *     applyArticlesToPage() нижче — навмисна заглушка з поясненням у коді.
 *
 * Вхід: шлях до layout_plan.json (записаного `inkforge-plan`) і шлях до
 * файла-основи (.indd попереднього випуску цієї газети).
 *
 * Запуск (для ручного тестування, коли план готовий):
 *   InDesign -> Window > Utilities > Scripts -> User -> запустити цей файл.
 *   Якщо app.scriptArgs не задані (звичайний запуск з панелі Scripts),
 *   скрипт запитає обидва файли через діалог вибору файлу.
 */

#target indesign

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
        // app.scriptArgs недоступний у деяких режимах запуску — це нормально
    }
    return null;
}

function pickFile(promptText, scriptArgKey) {
    var fromArgs = scriptArg(scriptArgKey);
    if (fromArgs) {
        return new File(fromArgs);
    }
    var picked = File.openDialog(promptText);
    if (!picked) {
        throw new Error("Файл не вибрано: " + promptText);
    }
    return picked;
}

function loadLayoutPlan(planFile) {
    var raw = readTextFile(planFile);
    // Сучасний ExtendScript (InDesign CC 2015+) має вбудований JSON.parse.
    // Якщо ваша версія InDesign старіша й JSON недоступний — оновіть InDesign
    // або підключіть окремий JSON-полiфіл перед цим викликом.
    return JSON.parse(raw);
}

/**
 * Preflight шрифтів: звіряє список очікуваних шрифтів (з профілю газети,
 * прокинутий у layout_plan.json) з реальним статусом шрифтів на цій машині.
 * Повертає масив рядків-попереджень; рішення "верстати попри це чи ні"
 * лишається за верстальницею (див. docs/architecture.md, "Ризик доступності
 * шрифтів").
 */
function checkFonts(plan) {
    var warnings = [];
    var expected = [].concat(plan.fonts_installed || [], plan.fonts_substituted || []);
    for (var i = 0; i < expected.length; i++) {
        var name = expected[i];
        var font = app.fonts.itemByName(name);
        if (!font.isValid) {
            warnings.push("Шрифт '" + name + "' не знайдено на цій машині взагалі.");
            continue;
        }
        if (font.status !== FontStatus.INSTALLED) {
            warnings.push(
                "Шрифт '" + name + "' наразі має статус " + font.status + " (очікувалось INSTALLED)."
            );
        }
    }
    return warnings;
}

/**
 * Запитує дату й номер випуску для колонтитула. Спершу пробує
 * app.scriptArgs (щоб у майбутньому Рівень 3 міг передати їх напряму без
 * діалогу), інакше показує простий діалог.
 */
function promptForIssueMeta() {
    var issueDate = scriptArg("issueDate");
    var issueNumber = scriptArg("issueNumber");
    if (issueDate && issueNumber) {
        return { issueDate: issueDate, issueNumber: issueNumber };
    }

    var dialog = new Window("dialog", "InkForge — дані випуску");
    dialog.add("statictext", undefined, "Дата випуску:");
    var dateField = dialog.add("edittext", undefined, issueDate || "");
    dateField.characters = 20;
    dialog.add("statictext", undefined, "Номер випуску:");
    var numberField = dialog.add("edittext", undefined, issueNumber || "");
    numberField.characters = 20;
    var buttons = dialog.add("group");
    buttons.add("button", undefined, "OK", { name: "ok" });
    buttons.add("button", undefined, "Скасувати", { name: "cancel" });
    if (dialog.show() !== 1) {
        throw new Error("Скасовано користувачем.");
    }
    return { issueDate: dateField.text, issueNumber: numberField.text };
}

/**
 * Проставляє текстові змінні колонтитула. Очікує, що вони вже визначені в
 * документі-основі (створюються один раз вручну: Type > Text Variables).
 */
function setRunningHeaderVariables(doc, issueDate, issueNumber) {
    var pairs = { InkForge_IssueDate: issueDate, InkForge_IssueNumber: issueNumber };
    for (var name in pairs) {
        if (!pairs.hasOwnProperty(name)) {
            continue;
        }
        var variable;
        try {
            variable = doc.textVariables.itemByName(name);
            if (!variable.isValid) {
                throw new Error("not found");
            }
        } catch (e) {
            $.writeln(
                "Змінна колонтитула '" + name + "' відсутня в документі — пропущено. " +
                "Створіть її вручну один раз (Type > Text Variables)."
            );
            continue;
        }
        variable.variableOptions.contents = String(pairs[name]);
    }
}

/**
 * ЗАГЛУШКА, навмисно не реалізована — див. коментар на початку файлу.
 * Коли profiles/<id>.yaml отримає мапу "роль статті -> Self ID фрейма" для
 * кожного автоматизованого розвороту, сюди додається реальна логіка:
 * очистити старий вміст фрейма, relink фото (itemLink.relink), застосувати
 * Horizontal Scale в межах 97-102%.
 */
function applyArticlesToPage(page, pagePlan) {
    $.writeln(
        "[TODO Рівень 2] Сторінка " + pagePlan.page + ": " + pagePlan.articles.length +
        " стаття(ей) заплановано, але розчищення/relink фреймів ще не реалізовано " +
        "(бракує мапи 'фрейм -> роль' у профілі газети)."
    );
}

function main() {
    var docFile = pickFile("Виберіть файл-основу (.indd) попереднього випуску:", "docPath");
    var planFile = pickFile("Виберіть layout_plan.json:", "planPath");
    var plan = loadLayoutPlan(planFile);

    var fontWarnings = checkFonts(plan);
    if (fontWarnings.length > 0) {
        alert("Попередження про шрифти:\n\n" + fontWarnings.join("\n"));
    }

    var meta = promptForIssueMeta();
    var doc = app.open(docFile);
    setRunningHeaderVariables(doc, meta.issueDate, meta.issueNumber);

    for (var i = 0; i < plan.pages.length; i++) {
        var pagePlan = plan.pages[i];
        if (pagePlan.status !== "planned") {
            continue; // ручні/спеціальні/поза межами/порожні сторінки не чіпаємо
        }
        var page = doc.pages.item(pagePlan.page - 1);
        applyArticlesToPage(page, pagePlan);
    }

    $.writeln(
        "Готово (частково): preflight шрифтів і колонтитул виконано, " +
        "розчищення/relink фреймів статей ще не автоматизовано."
    );
}

main();
