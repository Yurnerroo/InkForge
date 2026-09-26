/*
 * InkForge — Рівень 2, виконавець ExtendScript (Adobe InDesign).
 *
 * СТАТУС: частковий, НЕ перевірений на реальному InDesign (у середовищі
 * розробки немає встановленого InDesign). Реалізовано:
 *
 *   1. Preflight шрифтів — звірка layout_plan.json (fonts_installed /
 *      fonts_substituted, взяті з профілю газети) з реальним статусом
 *      шрифтів на цій машині через app.fonts.
 *   2. Простановка змінних колонтитула (дата випуску, номер) через
 *      Text Variables документа.
 *   3. Геометричне групування кількох статей на одному розвороті
 *      (findArticleClusters) + relink фото за знайденими кластерами
 *      (applyArticlesToPage) — ЛИШЕ для газет із розв'язаною мапою
 *      paragraph_style_roles (наразі тільки MIF; див.
 *      docs/architecture.md, "Групування кількох статей..."). Алгоритм
 *      перевірено на офлайн-аналізі IDML (samples/article_clusters.py,
 *      не в git), але НЕ на реальному InDesign — тому діє захисний
 *      принцип "не вгадувати": якщо кількість знайдених кластерів не
 *      збігається з кількістю запланованих статей, сторінка пропускається
 *      без жодних змін.
 *   4. Вставка реального тексту заголовка/ліда/тіла статті у знайдені
 *      фрейми (за роллю headline/lead_intro/body у кожному кластері),
 *      джерело — структурований розбір .docx/.txt у Рівні 1
 *      (content_checker.docreader). Якщо для статті title/lead/body
 *      порожні (Рівень 1 не зміг розпізнати структуру), відповідний
 *      фрейм лишається без змін, а не затирається порожнім текстом.
 *   5. Підтискання overset-тексту (fitFrameText) — якщо вставлений текст
 *      не поміщається у фрейм, Horizontal Scale поступово зменшується зі
 *      100% до нижньої межі з layout_plan.json (min_horizontal_scale,
 *      за замовчуванням 97%), як робить верстальниця вручну. Якщо текст
 *      лишається overset навіть на межі — пишеться попередження в лог,
 *      фрейм НЕ чіпається далі (зменшення/прибирання фото не
 *      автоматизовано, потребує підтвердження пріоритету дій у
 *      верстальниці).
 *   6. Чергування шрифту заголовка (applyHeadlineFontAlternation) — лише
 *      коли layout_plan.json несе підтверджене правило
 *      headline_font_alternation (наразі тільки "Ти і Я"; див.
 *      profiles/ty_i_ya.yaml): сусідні статті на сторінці отримують
 *      почергово різний з 2 заданих шрифтів. Якщо шрифт не встановлено на
 *      машині — пропускається з попередженням у лог, а не підміняється.
 *
 * ЩЕ НЕ РЕАЛІЗОВАНО (навмисно, не забуто):
 *   - Динамічне додавання/видалення фреймів під новий обсяг тексту, коли
 *     самого підтискання Horizontal Scale (п.5) недостатньо — точний
 *     пріоритет дій (зменшити фото → прибрати фото → ручне втручання)
 *     потребує підтвердження у верстальниці (див.
 *     docs/architecture.md, "Відкриті питання").
 *   - Духовність досі без мапи paragraph_style_roles, тому групування
 *     статей і все з нього залежне (relink фото, вставка тексту,
 *     fitFrameText) там взагалі не застосовується.
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
 * Перетворює profiles/*.yaml `paragraph_style_roles` (роль -> назва стилю
 * або масив назв) на зворотну мапу "назва стилю -> роль" для швидкого
 * пошуку під час обходу фреймів сторінки.
 */
function buildStyleToRoleMap(paragraphStyleRoles) {
    var styleToRole = {};
    for (var role in paragraphStyleRoles) {
        if (!paragraphStyleRoles.hasOwnProperty(role)) {
            continue;
        }
        var value = paragraphStyleRoles[role];
        var styleNames = (value instanceof Array) ? value : [value];
        for (var i = 0; i < styleNames.length; i++) {
            styleToRole[styleNames[i]] = role;
        }
    }
    return styleToRole;
}

/**
 * Геометричні межі pageItem у координатах сторінки: [y0, x0, y1, x1]
 * (той самий порядок, що повертає InDesign у geometricBounds).
 */
function itemBounds(item) {
    return item.geometricBounds;
}

/**
 * Довжина перетину двох діапазонів [x0, x1]; може бути 0 або від'ємною
 * (немає перетину).
 */
function xOverlap(a0, a1, b0, b1) {
    var lo = Math.max(a0, b0);
    var hi = Math.min(a1, b1);
    return hi - lo;
}

/**
 * Збирає всі текстові й графічні фрейми, розміщені на цій сторінці (сама
 * модель InDesign вже коректно прив'язує елементи до сторінки -- на
 * відміну від ручного парсингу IDML-XML, тут не потрібен окремий фільтр
 * "сміття на монтажному столі", InDesign сам його не поверне в page.*).
 * Повертає масив {item, kind, role, bounds}; role може бути null (не
 * підтримувана роль -- фрейм ігнорується подальшою кластеризацією, але
 * лишається в списку для діагностики).
 */
function collectPageFrames(page, styleToRole) {
    var frames = [];

    var textFrames = page.textFrames.everyItem().getElements();
    for (var i = 0; i < textFrames.length; i++) {
        var tf = textFrames[i];
        var role = null;
        try {
            if (tf.parentStory.paragraphs.length > 0) {
                role = styleToRole[tf.parentStory.paragraphs.item(0).appliedParagraphStyle.name] || null;
            }
        } catch (e) {
            role = null;
        }
        frames.push({ item: tf, kind: "text", role: role, bounds: itemBounds(tf) });
    }

    var photoCandidates = [].concat(
        page.rectangles.everyItem().getElements(),
        page.polygons.everyItem().getElements(),
        page.ovals.everyItem().getElements()
    );
    for (var j = 0; j < photoCandidates.length; j++) {
        var shape = photoCandidates[j];
        var hasImage = false;
        try {
            hasImage = shape.allGraphics.length > 0;
        } catch (e2) {
            hasImage = false;
        }
        if (hasImage) {
            frames.push({ item: shape, kind: "photo", role: "photo", bounds: itemBounds(shape) });
        }
    }

    return frames;
}

/**
 * Групує фрейми сторінки навколо кожного заголовка (роль "headline") --
 * перевірений на MIF алгоритм (див. docs/architecture.md, "Групування
 * кількох статей..."; samples/article_clusters.py -- офлайн-валідація на
 * реальних IDML-зразках). Повертає кластери у порядку читання заголовків
 * (згори вниз, потім зліва направо); "members" містить решту фреймів
 * (лід/тіло/фото), приписаних до цього заголовка.
 */
function findArticleClusters(page, styleToRole) {
    var frames = collectPageFrames(page, styleToRole);

    var headlines = [];
    for (var i = 0; i < frames.length; i++) {
        if (frames[i].role === "headline") {
            headlines.push(frames[i]);
        }
    }
    headlines.sort(function (a, b) {
        if (a.bounds[0] !== b.bounds[0]) {
            return a.bounds[0] - b.bounds[0];
        }
        return a.bounds[1] - b.bounds[1];
    });

    var clusters = [];
    for (var h = 0; h < headlines.length; h++) {
        clusters.push({ headline: headlines[h], members: [] });
    }

    for (var f = 0; f < frames.length; f++) {
        var frame = frames[f];
        if (frame.role === null || frame.role === "headline") {
            continue;
        }
        var candidates = [];
        for (var c = 0; c < headlines.length; c++) {
            if (headlines[c].bounds[0] <= frame.bounds[0] + 1) {
                candidates.push(c);
            }
        }
        if (candidates.length === 0) {
            continue; // немає заголовка вище -- лишається непризначеним, не вгадуємо
        }
        var sameColumn = [];
        for (var k = 0; k < candidates.length; k++) {
            var hl = headlines[candidates[k]];
            if (xOverlap(hl.bounds[1], hl.bounds[3], frame.bounds[1], frame.bounds[3]) > 0) {
                sameColumn.push(candidates[k]);
            }
        }
        var pool = sameColumn.length > 0 ? sameColumn : candidates;
        var bestIdx = pool[0];
        for (var p = 1; p < pool.length; p++) {
            if (headlines[pool[p]].bounds[0] > headlines[bestIdx].bounds[0]) {
                bestIdx = pool[p];
            }
        }
        clusters[bestIdx].members.push(frame);
    }

    return clusters;
}

/**
 * Знаходить перший member-фрейм з роллю "photo" у кластері, або null.
 */
function findPhotoMember(cluster) {
    for (var i = 0; i < cluster.members.length; i++) {
        if (cluster.members[i].role === "photo") {
            return cluster.members[i];
        }
    }
    return null;
}

/**
 * Знаходить перший member-фрейм з заданою роллю (напр. "lead_intro" чи
 * "body") у кластері, або null.
 */
function findMemberByRole(cluster, role) {
    for (var i = 0; i < cluster.members.length; i++) {
        if (cluster.members[i].role === role) {
            return cluster.members[i];
        }
    }
    return null;
}

/**
 * Вставляє текст у фрейм замість поточного вмісту story. Абзаци у "text"
 * розділені "\n" (формат Рівня 1) -- перед вставкою заміняються на "\r"
 * (розрив абзацу в InDesign). Якщо "text" порожній -- нічого не робить і
 * повертає false (захисний принцип: не затирати наявний вміст фрейму,
 * якщо Рівень 1 не дав структурованого тексту для цієї статті).
 */
function setFrameText(item, text) {
    if (!text) {
        return false;
    }
    try {
        item.parentStory.contents = String(text).replace(/\n/g, "\r");
        return true;
    } catch (e) {
        return false;
    }
}

/**
 * Якщо вставлений текст не поміщається у фрейм (overset), пробує "підтиснути"
 * його через Horizontal Scale, крок за кроком зменшуючи від 100% до
 * "minScale" (нижня межа з layout_plan.json, за замовчуванням 97% --
 * див. docs/architecture.md, "Рівень 2"), як робить верстальниця вручну.
 * Це єдиний автоматичний спосіб боротьби з overset -- зменшення/прибирання
 * фото НЕ автоматизовано (потребує підтвердження пріоритету дій у
 * верстальниці, див. "Відкриті питання"). Верхня межа (max_horizontal_scale,
 * за замовчуванням 102%) зарезервована на майбутнє для протилежної задачі
 * (розтягнути закороткий текст) -- тут не використовується. Повертає true,
 * якщо текст вміщається (одразу або після підтискання); false, якщо лишився
 * overset навіть на мінімальному масштабі -- потребує ручного втручання.
 */
function fitFrameText(item, minScale) {
    try {
        if (!item.overflows) {
            return true;
        }
    } catch (e) {
        return true; // немає способу перевірити overset -- не гадаємо, лишаємо як є
    }

    var scale = 100;
    while (item.overflows && scale > minScale) {
        scale -= 1;
        try {
            item.texts[0].horizontalScale = scale;
        } catch (e2) {
            break;
        }
    }

    return !item.overflows;
}

/**
 * Застосовує підтверджене верстальницею правило чергування шрифту
 * заголовка (див. profiles/ty_i_ya.yaml, поле headline_font_alternation):
 * сусідні статті на одній сторінці отримують почергово різний шрифт із
 * "fonts" (за порядком читання -- той самий порядок кластерів, що й у
 * findArticleClusters/applyArticlesToPage). "articleIndex" -- 0-базований
 * індекс статті В МЕЖАХ ЦІЄЇ СТОРІНКИ (не всього номера), бо чергування
 * підтверджено саме "на одній сторінці".
 *
 * Захисний принцип: якщо правило не підтверджено (`confirmed !== true`),
 * не задано, чи задано менше 2 шрифтів -- нічого не робить. Якщо потрібний
 * шрифт не встановлено на цій машині -- лише пише попередження в лог і не
 * чіпає фрейм (не підставляємо інший шрифт замість нього).
 */
function applyHeadlineFontAlternation(item, plan, articleIndex, pageNumber, slug) {
    var alternation = plan.headline_font_alternation;
    if (!alternation || alternation.confirmed !== true) {
        return;
    }
    var fonts = alternation.fonts;
    if (!fonts || fonts.length < 2) {
        return;
    }

    var fontName = fonts[articleIndex % fonts.length];
    var font = app.fonts.itemByName(fontName);
    if (!font.isValid) {
        $.writeln(
            "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug + "': шрифт '" + fontName +
            "' для чергування заголовка не знайдено на цій машині -- пропущено без змін."
        );
        return;
    }

    try {
        item.texts[0].appliedFont = font;
        try {
            item.texts[0].fontStyle = "Bold";
        } catch (styleErr) {
            $.writeln(
                "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug + "': шрифт '" + fontName +
                "' встановлено, але стиль 'Bold' для нього недоступний (" + styleErr + ")."
            );
        }
        $.writeln(
            "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug +
            "': шрифт заголовка встановлено на '" + fontName + "' (чергування, позиція " +
            articleIndex + " на сторінці)."
        );
    } catch (e) {
        $.writeln(
            "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug +
            "': НЕ вдалося застосувати шрифт '" + fontName + "' (" + e + ")."
        );
    }
}

/**
 * Групує сторінку за геометрією, (для фото) переприв'язує посилання на
 * нові файли зі layout_plan.json і вставляє текст заголовка/ліда/тіла
 * статті у відповідні за роллю фрейми (headline / lead_intro / body).
 *
 * Захисний принцип: якщо мапа ролей для газети ще "TBD", або кількість
 * знайдених кластерів не збігається з кількістю запланованих статей --
 * сторінка пропускається без жодних змін (краще нічого не зробити, ніж
 * вгадати неправильно). Так само, якщо для статті немає title/lead/body
 * (Рівень 1 не зміг їх розпізнати) -- відповідний фрейм лишається без
 * змін, а не затирається порожнім текстом.
 */
function applyArticlesToPage(page, pagePlan, plan) {
    if (!plan.paragraph_style_roles || typeof plan.paragraph_style_roles !== "object") {
        $.writeln(
            "[Рівень 2] Сторінка " + pagePlan.page + ": paragraph_style_roles для газети '" +
            plan.newspaper_id + "' ще не розв'язано (\"TBD\") -- групування статей і relink " +
            "фото пропущено для цієї сторінки."
        );
        return;
    }

    var styleToRole = buildStyleToRoleMap(plan.paragraph_style_roles);
    var clusters = findArticleClusters(page, styleToRole);

    if (clusters.length !== pagePlan.articles.length) {
        $.writeln(
            "[Рівень 2] Сторінка " + pagePlan.page + ": знайдено " + clusters.length +
            " кластер(и/ів) заголовків, але заплановано " + pagePlan.articles.length +
            " статей(і) -- пропущено без змін (не вгадуємо парування)."
        );
        return;
    }

    var articles = pagePlan.articles.slice().sort(function (a, b) {
        return a.order - b.order;
    });

    for (var i = 0; i < clusters.length; i++) {
        var cluster = clusters[i];
        var article = articles[i];
        var photoMember = findPhotoMember(cluster);

        if (photoMember && article.image_path) {
            try {
                photoMember.item.allGraphics[0].itemLink.relink(new File(article.image_path));
                $.writeln(
                    "[Рівень 2] Сторінка " + pagePlan.page + ", стаття '" + article.slug +
                    "': фото переприв'язано на " + article.image_path + "."
                );
            } catch (e) {
                $.writeln(
                    "[Рівень 2] Сторінка " + pagePlan.page + ", стаття '" + article.slug +
                    "': НЕ вдалося переприв'язати фото (" + e + ")."
                );
            }
        }

        $.writeln(
            "[Рівень 2] Сторінка " + pagePlan.page + ": заголовковий фрейм (id " + cluster.headline.item.id +
            ") <-> стаття '" + article.slug + "'."
        );

        var leadMember = findMemberByRole(cluster, "lead_intro");
        var bodyMember = findMemberByRole(cluster, "body");
        var minScale = plan.min_horizontal_scale || 97;

        var inserted = [];
        var skipped = [];
        var overset = [];

        if (setFrameText(cluster.headline.item, article.title)) {
            inserted.push("заголовок");
            if (!fitFrameText(cluster.headline.item, minScale)) {
                overset.push("заголовок");
            }
            applyHeadlineFontAlternation(cluster.headline.item, plan, i, pagePlan.page, article.slug);
        } else {
            skipped.push("заголовок");
        }

        if (leadMember) {
            if (setFrameText(leadMember.item, article.lead)) {
                inserted.push("лід");
                if (!fitFrameText(leadMember.item, minScale)) {
                    overset.push("лід");
                }
            } else {
                skipped.push("лід");
            }
        }

        if (bodyMember) {
            if (setFrameText(bodyMember.item, article.body)) {
                inserted.push("тіло");
                if (!fitFrameText(bodyMember.item, minScale)) {
                    overset.push("тіло");
                }
            } else {
                skipped.push("тіло");
            }
        }

        $.writeln(
            "[Рівень 2] Сторінка " + pagePlan.page + ", стаття '" + article.slug + "': вставлено (" +
            (inserted.length > 0 ? inserted.join(", ") : "нічого") + "); пропущено без змін (" +
            (skipped.length > 0 ? skipped.join(", ") : "нічого") + ")."
        );

        if (overset.length > 0) {
            $.writeln(
                "[Рівень 2] Сторінка " + pagePlan.page + ", стаття '" + article.slug +
                "': УВАГА -- текст не поміщається навіть при Horizontal Scale " + minScale +
                "% (" + overset.join(", ") + ") -- потрібне ручне втручання верстальниці."
            );
        }
    }
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
        applyArticlesToPage(page, pagePlan, plan);
    }

    $.writeln(
        "Готово (частково): preflight шрифтів, колонтитул, геометричне групування статей, " +
        "relink фото, вставка тексту заголовка/ліда/тіла, підтискання overset-тексту " +
        "(Horizontal Scale) та чергування шрифту заголовка (де підтверджено) виконано для " +
        "газет із розв'язаною мапою ролей (paragraph_style_roles); перевірка на реальному " +
        "InDesign ще потрібна."
    );
}

main();
