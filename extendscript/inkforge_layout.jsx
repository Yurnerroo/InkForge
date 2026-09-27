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
  *      (applyArticlesToPage) — коли є розв'язана мапа
  *      paragraph_style_roles (наразі MIF; див. docs/architecture.md,
  *      "Групування кількох статей...") АБО, якщо її немає,
  *      character_size_roles як fallback-класифікація ролі фрейму за
  *      character-level розміром шрифту (лише бінарний headline/body,
  *      наразі Духовність; див. resolveRoleByCharacterSize нижче).
  *      Алгоритм перевірено на офлайн-аналізі IDML
  *      (samples/article_clusters.py, не в git), але НЕ на реальному
  *      InDesign — тому діє захисний принцип "не вгадувати": якщо
  *      кількість знайдених кластерів не збігається з кількістю
  *      запланованих статей, сторінка пропускається без жодних змін.
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
 *   - Духовність: character_size_roles дає лише бінарний headline/body —
  *     градація підзаголовок/кікер/лід (lead_intro) для цієї газети
  *     невідома, тому lead-фрейм там просто не заповнюється (немає такої
  *     ролі), а не вгадується.
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

// ExtendScript -- це ES3-рушій і НЕ має вбудованого JSON.parse/stringify
// (на відміну від сучасного браузерного/Node.js JS). Підключаємо
// стандартний публічний поліфіл (Дуглас Крокфорд, json2.js), який сам
// нічого не робить, якщо JSON вже є в середовищі.
#include "vendor/json2.jsx"

// $.writeln пише лише в ExtendScript-консоль, яку launcher НЕ бачить (COM
// DoScript не перехоплює цей потік) — тому раніше всі попередження про
// пропущені сторінки/фрейми "губилися": launcher показував "Готово" навіть
// якщо всю сторінку 2 чи 3 мовчки пропущено через невідповідність кількості
// кластерів. RUN_LOG/log() дублює кожне повідомлення і в консоль (для
// ручного відлагодження в InDesign), і в масив, що main() повертає одним
// рядком — DoScript вже прокидає цей рядок у Python (indesign_bridge.py)
// і в JSON-відповідь /api/execute, де launcher UI його показує.
var RUN_LOG = [];
// Сторінки, пропущені захисним принципом "не вгадувати" (невідповідна
// кількість кластерів/ролей) -- НЕ ручні сторінки на кшталт 8, а справжні
// збої автоматизації, які варто показати верстальниці окремим підсумком.
var SKIPPED_PAGES = [];

function log(message) {
    $.writeln(message);
    RUN_LOG.push(message);
}

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
            log(
                "Змінна колонтитула '" + name + "' відсутня в документі — пропущено. " +
                "Створіть її вручну один раз (Type > Text Variables)."
            );
            continue;
        }
        variable.variableOptions.contents = String(pairs[name]);
    }
}

/**
 * Короткий опис кластера для діагностики розбіжності "кластерів != статей"
 * -- ID фрейму заголовка, його геометричні межі (у форматі InDesign
 * geometricBounds: [y1, x1, y2, x2], пункти від верхнього лівого кута
 * сторінки/розвороту) і перші ~40 символів тексту, щоб верстальниця могла
 * впізнати, якій реальній статті/сторінці належить цей фрейм -- зокрема
 * підтвердити чи спростувати підозру про фрейми "чужої" сторінки розвороту
 * (напр. фрейм зі сторінки 3, що потрапив у кластери сторінки 2).
 */
function describeClusterForLog(cluster) {
    var headlineText = "";
    try {
        headlineText = cluster.headline.item.contents;
        if (headlineText && headlineText.length > 40) {
            headlineText = headlineText.substr(0, 40) + "...";
        }
    } catch (e) {
        headlineText = "(не вдалося прочитати текст)";
    }
    var bounds = cluster.headline.bounds;
    return "id=" + cluster.headline.item.id +
        (cluster.headline.isComboHeadline ? " (комбо: заголовок+тіло в одному фреймі)" : "") +
        ", bounds=[" + bounds.join(", ") + "], текст=\"" + headlineText + "\"";
}

/**
 * Короткий опис БУДЬ-ЯКОГО фрейму сторінки (не лише заголовкового) для
 * діагностики розбіжності "кластерів != статей" -- показує саме роль і
 * назву стилю абзаца, розв'язані collectPageFrames, щоб було видно, чому
 * конкретний фрейм НЕ потрапив у "headline" (стиль не входить у
 * paragraph_style_roles профілю? стиль зчитався як null? роль інша?).
 */
function describeFrameForLog(frame) {
    var text = "";
    try {
        text = frame.item.contents;
        if (text && text.length > 40) {
            text = text.substr(0, 40) + "...";
        }
    } catch (e) {
        text = "(не вдалося прочитати текст)";
    }
    return "id=" + frame.item.id + ", kind=" + frame.kind + ", role=" +
        (frame.role === null ? "null" : frame.role) + ", styleName=" +
        (frame.styleName ? "\"" + frame.styleName + "\"" : "(немає)") +
        ", bounds=[" + frame.bounds.join(", ") + "], текст=\"" + text + "\"";
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
 * Fallback-класифікація ролі текстового фрейму за character-level
 * розміром шрифту (profiles/*.yaml поле `character_size_roles`) -- для
 * газет без надійної мапи `paragraph_style_roles` (наразі Духовність, див.
 * docs/architecture.md). Підтверджено лише БІНАРНИЙ поділ: "headline"
 * (переважає символів із pointSize >= headline_like_point_size_min) чи
 * "body" (переважає символів із pointSize <= body_point_size_max); якщо
 * жодна група символів не переважає (або фрейм порожній) -- повертає null,
 * не вгадуємо. Рахуємо саме символи (не абзаци/textStyleRange), щоб
 * короткий заголовок великим кеглем не програвав довшому тілу тексту
 * дрібним кеглем. Припущення (не перевірене на реальному InDesign):
 * заголовок і тіло статті лежать у РІЗНИХ текстових фреймах -- те саме
 * припущення, на якому вже стоїть уся роль-система для MIF.
 */
function resolveRoleByCharacterSize(tf, sizeRoles) {
    var bodyMax = sizeRoles.body_point_size_max;
    var headlineMin = sizeRoles.headline_like_point_size_min;
    if (typeof bodyMax !== "number" || typeof headlineMin !== "number") {
        return null;
    }

    var bodyChars = 0;
    var headlineChars = 0;
    try {
        var ranges = tf.parentStory.textStyleRanges.everyItem().getElements();
        for (var i = 0; i < ranges.length; i++) {
            var size = ranges[i].pointSize;
            var len = ranges[i].characters.length;
            if (size <= bodyMax) {
                bodyChars += len;
            } else if (size >= headlineMin) {
                headlineChars += len;
            }
        }
    } catch (e) {
        return null;
    }

    if (headlineChars === 0 && bodyChars === 0) {
        return null;
    }
    return headlineChars > bodyChars ? "headline" : "body";
}

/**
 * Збирає всі текстові й графічні фрейми, розміщені на цій сторінці (сама
 * модель InDesign вже коректно прив'язує елементи до сторінки -- на
 * відміну від ручного парсингу IDML-XML, тут не потрібен окремий фільтр
 * "сміття на монтажному столі", InDesign сам його не поверне в page.*).
 * Повертає масив {item, kind, role, bounds}; role може бути null (не
 * підтримувана роль -- фрейм ігнорується подальшою кластеризацією, але
 * лишається в списку для діагностики). "sizeRoles" (profiles/*.yaml поле
 * `character_size_roles`) -- опціональний fallback, коли роль за стилем
 * абзацу не визначилась (null/невідомий стиль); передайте null, щоб його
 * не використовувати.
 */
function collectPageFrames(page, styleToRole, sizeRoles) {
    var frames = [];

    var textFrames = page.textFrames.everyItem().getElements();
    for (var i = 0; i < textFrames.length; i++) {
        var tf = textFrames[i];
        var role = null;
        var styleName = null;
        var paragraphCount = 0;
        try {
            paragraphCount = tf.parentStory.paragraphs.length;
            if (paragraphCount > 0) {
                styleName = tf.parentStory.paragraphs.item(0).appliedParagraphStyle.name;
                role = styleToRole[styleName] || null;
            }
        } catch (e) {
            role = null;
        }
        if (role === null && sizeRoles) {
            role = resolveRoleByCharacterSize(tf, sizeRoles);
        }
        // "styleName" -- лише для діагностики (describeFrameForLog): яка
        // назва стилю абзацу реально застосована, навіть якщо роль не
        // розв'язалась -- саме це потрібно, щоб зрозуміти, чому фрейм не
        // потрапив у кластер заголовків (стиль не в paragraph_style_roles?
        // порожній фрейм? інша роль?). "paragraphCount" -- потрібен для
        // "комбо"-евристики в findArticleClusters (див. коментар там):
        // фрейм зі стилем "kicker_or_page_badge", але з КІЛЬКОМА абзацами
        // -- це не рубрика/номер сторінки, а ціла міні-стаття
        // заголовок+тіло в одному фреймі.
        frames.push({
            item: tf,
            kind: "text",
            role: role,
            bounds: itemBounds(tf),
            styleName: styleName,
            paragraphCount: paragraphCount
        });
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
 * "Комбо"-евристика для findArticleClusters: у реальних шаблонах MIF роль
 * "kicker_or_page_badge" (стиль Zag_small) насправді перевикористовується
 * для ТРЬОХ різних речей -- (1) мітка рубрики в один рядок ("треба
 * знати"), (2) бейдж номера сторінки (одна цифра), і (3) ціла міні-стаття
 * "заголовок+тіло" в ОДНОМУ текстовому фреймі (коротка замітка без
 * окремого лід/тіло-фрейму). Випадки (1)/(2) -- завжди ОДИН абзац;
 * випадок (3) -- ЗАВЖДИ кілька абзаців (заголовок + хоч один абзац тіла).
 * Це підтверджений на реальних сторінках MIF (2, 3, 7) сигнал: якщо
 * кількість абзаців у фреймі з цією роллю >= COMBO_MIN_PARAGRAPHS, фрейм
 * трактується як додатковий кандидат-заголовок статті (isComboHeadline),
 * а не як кікер/номер сторінки. Ризик хибного спрацювання лишається (див.
 * docs/architecture.md, "Групування кількох статей..."), тож це не
 * ввімкнено для інших ролей -- лише для цієї конкретної, вже підтвердженої
 * неоднозначності.
 */
var COMBO_ELIGIBLE_ROLE = "kicker_or_page_badge";
var COMBO_MIN_PARAGRAPHS = 2;

/**
 * Групує фрейми сторінки навколо кожного заголовка (роль "headline", або
 * "комбо"-кандидат -- див. COMBO_ELIGIBLE_ROLE вище) -- перевірений на MIF
 * алгоритм (див. docs/architecture.md, "Групування кількох статей...";
 * samples/article_clusters.py -- офлайн-валідація на реальних
 * IDML-зразках). Повертає кластери у порядку читання заголовків (згори
 * вниз, потім зліва направо); "members" містить решту фреймів
 * (лід/тіло/фото), приписаних до цього заголовка -- для комбо-кластерів
 * зазвичай ПОРОЖНІЙ (увесь вміст уже лежить у самому headline-фреймі, див.
 * cluster.headline.isComboHeadline в applyArticlesToPage).
 */
function findArticleClusters(page, styleToRole, sizeRoles) {
    var frames = collectPageFrames(page, styleToRole, sizeRoles);

    var headlines = [];
    for (var i = 0; i < frames.length; i++) {
        var f = frames[i];
        if (f.role === "headline") {
            f.isComboHeadline = false;
            headlines.push(f);
        } else if (f.kind === "text" && f.role === COMBO_ELIGIBLE_ROLE &&
            f.paragraphCount >= COMBO_MIN_PARAGRAPHS) {
            f.isComboHeadline = true;
            headlines.push(f);
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

    for (var f2 = 0; f2 < frames.length; f2++) {
        var frame = frames[f2];
        if (frame.role === null || frame.role === "headline" || frame.isComboHeadline) {
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
 * Повертає першу назву стилю для заданої ролі з profiles/*.yaml
 * `paragraph_style_roles` (значення може бути рядком або масивом назв) --
 * або null, якщо роль не задана чи мапа відсутня.
 */
function firstStyleNameForRole(paragraphStyleRoles, role) {
    if (!paragraphStyleRoles || typeof paragraphStyleRoles !== "object") {
        return null;
    }
    var value = paragraphStyleRoles[role];
    if (!value) {
        return null;
    }
    return (value instanceof Array) ? (value.length > 0 ? value[0] : null) : value;
}

/**
 * Застосовує стиль абзацу-підзаголовка (paragraph_style_roles.subheadline
 * з profiles/*.yaml) до вказаних абзаців історії фрейму за їхніми 0-based
 * індексами (мають відповідати позиціям абзаців "\n"-розділеного body
 * після вставки через setFrameText -- порядок гарантовано збігається, бо
 * setFrameText лише міняє "\n" на "\r", не змінюючи кількість/порядок
 * абзаців). Мовчки нічого не робить, якщо indices порожній, стиль не
 * задано, або сам стиль не знайдено в документі (профіль газети без ролі
 * "subheadline" -- не помилка, просто фіча не застосовується).
 */
function applySubheadingStyles(item, indices, subheadStyleName) {
    if (!indices || indices.length === 0 || !subheadStyleName) {
        return;
    }
    var style;
    try {
        var doc = item.parentStory.parent;
        style = doc.paragraphStyles.itemByName(subheadStyleName);
        if (!style.isValid) {
            return;
        }
    } catch (e) {
        return;
    }
    var paragraphs = item.parentStory.paragraphs;
    for (var i = 0; i < indices.length; i++) {
        var idx = indices[i];
        try {
            if (idx >= 0 && idx < paragraphs.length) {
                paragraphs.item(idx).appliedParagraphStyle = style;
            }
        } catch (e) {
            // Best effort -- one bad index shouldn't block the rest of layout.
        }
    }
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
        log(
            "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug + "': шрифт '" + fontName +
            "' для чергування заголовка не знайдено на цій машині -- пропущено без змін."
        );
        return;
    }

    try {
        // Застосовуємо лише до ПЕРШОГО абзацу (не всього item.texts[0]) --
        // для звичайного окремого заголовкового фрейму це те саме (там і
        // так лише один абзац), а для "комбо"-фрейму (заголовок+тіло в
        // одній історії, див. COMBO_ELIGIBLE_ROLE) це критично: інакше
        // чергування шрифту зачепило б і текст тіла статті, а не лише
        // заголовок.
        var headlineRange = item.paragraphs.item(0).texts[0];
        headlineRange.appliedFont = font;
        try {
            headlineRange.fontStyle = "Bold";
        } catch (styleErr) {
            log(
                "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug + "': шрифт '" + fontName +
                "' встановлено, але стиль 'Bold' для нього недоступний (" + styleErr + ")."
            );
        }
        log(
            "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug +
            "': шрифт заголовка встановлено на '" + fontName + "' (чергування, позиція " +
            articleIndex + " на сторінці)."
        );
    } catch (e) {
        log(
            "[Рівень 2] Сторінка " + pageNumber + ", стаття '" + slug +
            "': НЕ вдалося застосувати шрифт '" + fontName + "' (" + e + ")."
        );
    }
}

/**
 * Лінійний пошук елемента сторінки за точним числовим "id" (scripting
 * property порядкового номера елемента, не Self ID з IDML-файлу напряму --
 * hex-рядок з profiles/mif.yaml.page1_layout переводиться в число викликом
 * коду, що використовує цю функцію, через parseInt(hexId, 16)).
 *
 * Свідомо НЕ використовує itemByID() -- семантика цього методу (чи він
 * шукає по всьому документу, чи лише в межах сторінки/розвороту виклику, і
 * як реагує на відсутній ID) не перевірена (немає InDesign у середовищі
 * розробки цього проєкту), тож обрано консервативніший, самоочевидний
 * підхід: пройтися по колекціях сторінки й порівняти .id напряму.
 */
function findByExactId(page, numericId) {
    var collections = [
        page.textFrames.everyItem().getElements(),
        page.rectangles.everyItem().getElements(),
        page.polygons.everyItem().getElements(),
        page.ovals.everyItem().getElements()
    ];
    for (var c = 0; c < collections.length; c++) {
        var collection = collections[c];
        for (var i = 0; i < collection.length; i++) {
            if (collection[i].id === numericId) {
                return collection[i];
            }
        }
    }
    return null;
}

/**
 * Знаходить першу статтю з заданою роллю (role, напр. "main" чи
 * "storm_forecast" -- див. planner._plan_page1_special) серед статей
 * сторінки, або null.
 */
function findArticleByRole(articles, role) {
    for (var i = 0; i < articles.length; i++) {
        if (articles[i].role === role) {
            return articles[i];
        }
    }
    return null;
}

/**
 * Переприв'язує головне фото сторінки 1 (фіксований frame ID з
 * page1_layout.main_photo_frame_id) на зображення головної статті.
 * Захисний принцип, як і в applyArticlesToPage: будь-яка невдача (не
 * знайдено фрейм, немає image_path, помилка relink) лише пишеться у
 * $.writeln і пропускається без здогадок.
 */
function applyPage1PhotoSlot(page, hexId, article, pageNumber) {
    var numericId = parseInt(hexId, 16);
    if (isNaN(numericId)) {
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: некоректний ID '" + hexId +
            "' для головного фото -- пропущено."
        );
        return;
    }
    var frame = findByExactId(page, numericId);
    if (!frame) {
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: фрейм з id " + hexId +
            " (головне фото) не знайдено на сторінці -- пропущено."
        );
        return;
    }
    if (!article.image_path) {
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: для головної статті '" +
            article.slug + "' немає image_path -- фото не переприв'язано."
        );
        return;
    }
    try {
        frame.allGraphics[0].itemLink.relink(new File(article.image_path));
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: головне фото переприв'язано на " +
            article.image_path + "."
        );
    } catch (e) {
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: НЕ вдалося переприв'язати головне " +
            "фото (" + e + ")."
        );
    }
}

/**
 * Вставляє текст у фіксований (за hex ID з page1_layout) фрейм сторінки 1
 * і намагається підтиснути overset так само, як applyArticlesToPage.
 * "subheadingIndices"/"subheadStyleName" опціональні -- передаються лише
 * для тіла статті (заголовок підзаголовків не має).
 */
function applyPage1TextSlot(page, hexId, text, minScale, pageNumber, label, subheadingIndices, subheadStyleName) {
    var numericId = parseInt(hexId, 16);
    if (isNaN(numericId)) {
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: некоректний ID '" + hexId +
            "' для " + label + " -- пропущено."
        );
        return;
    }
    var frame = findByExactId(page, numericId);
    if (!frame) {
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: фрейм з id " + hexId + " (" + label +
            ") не знайдено на сторінці -- пропущено."
        );
        return;
    }
    if (setFrameText(frame, text)) {
        applySubheadingStyles(frame, subheadingIndices, subheadStyleName);
        if (!fitFrameText(frame, minScale)) {
            log(
                "[Рівень 2, стор." + pageNumber + "] page1_layout: " + label + " не поміщається " +
                "навіть при Horizontal Scale " + minScale + "% -- потрібне ручне втручання " +
                "верстальниці."
            );
        }
    } else {
        log(
            "[Рівень 2, стор." + pageNumber + "] page1_layout: " + label + " -- немає тексту для " +
            "вставки (пропущено без змін)."
        );
    }
}

/**
 * Спеціальна обробка сторінки 1 МІФ (status="planned_page1_special" у
 * layout_plan.json). На відміну від findArticleClusters/applyArticlesToPage
 * (геометричне кластерування для сторінок 2-7 і Диховності), тут
 * підставляються фіксовані IDML Self ID з profiles/mif.yaml.page1_layout,
 * знайдені й перевірені на стабільність по 3 зразках issue07/08/09 --
 * сторінка 1 має ~38 текстових фреймів (шапка, штрих-код, тизери інших
 * сторінок тощо), для яких геометричне кластерування не підходить (його
 * захисний принцип "кількість кластерів != кількість статей -- пропустити
 * всю сторінку" майже напевно спрацював би хибно на такій кількості
 * непов'язаних елементів).
 *
 * Правила (підтверджені верстальницею, див. profiles/mif.yaml):
 *   - роль "main" (найдовша стаття, окрім прогнозу магнітних бур) --
 *     велике фото зліва + заголовок + тіло у фіксовані фрейми.
 *   - роль "storm_forecast" (стаття з ключовим словом
 *     storm_forecast_keyword) -- один фрейм, що вже має кольоровий фон у
 *     шаблоні (перевірено на зразках) -- скрипт лише вставляє заголовок і
 *     тіло одним блоком, колір не чіпає.
 * "Народні прикмети" СВІДОМО не автоматизовано (жодного разу не було
 * фактично розміщено на сторінці в 3 зразках -- див. profiles/mif.yaml) --
 * лишається ручною вставкою верстальниці.
 */
function applyMifPage1Special(page, pagePlan, plan) {
    var layout = plan.page1_layout;
    if (!layout) {
        log(
            "[Рівень 2, стор." + pagePlan.page + "] page1_layout відсутній у плані -- пропущено."
        );
        SKIPPED_PAGES.push(pagePlan.page + " (немає page1_layout у плані)");
        return;
    }
    var minScale = plan.min_horizontal_scale || 97;
    var subheadStyleName = firstStyleNameForRole(plan.paragraph_style_roles, "subheadline");

    var mainArticle = findArticleByRole(pagePlan.articles, "main");
    if (mainArticle) {
        applyPage1PhotoSlot(page, layout.main_photo_frame_id, mainArticle, pagePlan.page);
        applyPage1TextSlot(
            page, layout.main_headline_frame_id, mainArticle.title, minScale, pagePlan.page,
            "заголовок головної статті"
        );
        applyPage1TextSlot(
            page, layout.main_body_frame_id, mainArticle.body, minScale, pagePlan.page,
            "тіло головної статті", mainArticle.subheading_indices, subheadStyleName
        );
    } else {
        log(
            "[Рівень 2, стор." + pagePlan.page + "] page1_layout: роль 'main' не призначено жодній " +
            "статті -- фото/заголовок/тіло головної статті не змінено."
        );
    }

    var stormArticle = findArticleByRole(pagePlan.articles, "storm_forecast");
    if (stormArticle) {
        var stormText = stormArticle.title
            ? stormArticle.title + "\n" + stormArticle.body
            : stormArticle.body;
        applyPage1TextSlot(
            page, layout.storm_forecast_frame_id, stormText, minScale, pagePlan.page,
            "прогноз магнітних бур"
        );
    } else {
        log(
            "[Рівень 2, стор." + pagePlan.page + "] page1_layout: роль 'storm_forecast' не " +
            "призначено жодній статті -- прогноз магнітних бур не змінено."
        );
    }

    log(
        "[Рівень 2, стор." + pagePlan.page + "] page1_layout: спеціальна обробка сторінки 1 " +
        "завершена (\"Народні прикмети\" свідомо не автоматизовано)."
    );
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
    var hasStyleRoles = plan.paragraph_style_roles && typeof plan.paragraph_style_roles === "object";
    var hasSizeRoles = plan.character_size_roles && typeof plan.character_size_roles === "object" &&
        typeof plan.character_size_roles.body_point_size_max === "number" &&
        typeof plan.character_size_roles.headline_like_point_size_min === "number";

    if (!hasStyleRoles && !hasSizeRoles) {
        log(
            "[Рівень 2] Сторінка " + pagePlan.page + ": ні paragraph_style_roles, ні " +
            "character_size_roles для газети '" + plan.newspaper_id + "' не розв'язано -- " +
            "групування статей і relink фото пропущено для цієї сторінки."
        );
        SKIPPED_PAGES.push(pagePlan.page + " (немає paragraph_style_roles/character_size_roles)");
        return;
    }

    var styleToRole = hasStyleRoles ? buildStyleToRoleMap(plan.paragraph_style_roles) : {};
    var sizeRoles = hasSizeRoles ? plan.character_size_roles : null;
    var subheadStyleName = hasStyleRoles ? firstStyleNameForRole(plan.paragraph_style_roles, "subheadline") : null;
    var clusters = findArticleClusters(page, styleToRole, sizeRoles);

    if (clusters.length !== pagePlan.articles.length) {
        log(
            "[Рівень 2] Сторінка " + pagePlan.page + ": знайдено " + clusters.length +
            " кластер(и/ів) заголовків, але заплановано " + pagePlan.articles.length +
            " статей(і) -- пропущено без змін (не вгадуємо парування)."
        );
        for (var ci = 0; ci < clusters.length; ci++) {
            log(
                "[Рівень 2] Сторінка " + pagePlan.page + ": кластер #" + (ci + 1) + " -- " +
                describeClusterForLog(clusters[ci])
            );
        }
        // Розбіжність найчастіше означає, що частина фреймів на сторінці
        // НЕ отримала роль "headline", хоча має бути окремою статтею --
        // покажемо буквально всі текстові/фото-фрейми сторінки з їхньою
        // роллю й реальною назвою стилю абзаца, щоб було видно, чи стиль
        // просто не входить у paragraph_style_roles профілю (типова
        // причина: секондарний заголовок отримав інший/ручний стиль).
        var allFrames = collectPageFrames(page, styleToRole, sizeRoles);
        for (var fi = 0; fi < allFrames.length; fi++) {
            log(
                "[Рівень 2] Сторінка " + pagePlan.page + ": фрейм #" + (fi + 1) + " -- " +
                describeFrameForLog(allFrames[fi])
            );
        }
        SKIPPED_PAGES.push(
            pagePlan.page + " (кластерів: " + clusters.length + ", статей у плані: " +
            pagePlan.articles.length + ")"
        );
        return;
    }

    // Tie-break on sub_order (present when several articles were split out
    // of one multi-article source file and share the same order) -- the
    // ExtendScript engine's Array.sort is not guaranteed stable, so an
    // explicit compound key is required here even though Python's sort
    // already handles this correctly via stability alone.
    var articles = pagePlan.articles.slice().sort(function (a, b) {
        if (a.order !== b.order) return a.order - b.order;
        return (a.sub_order || 0) - (b.sub_order || 0);
    });

    for (var i = 0; i < clusters.length; i++) {
        var cluster = clusters[i];
        var article = articles[i];
        var photoMember = findPhotoMember(cluster);

        if (photoMember && article.image_path) {
            try {
                photoMember.item.allGraphics[0].itemLink.relink(new File(article.image_path));
                log(
                    "[Рівень 2] Сторінка " + pagePlan.page + ", стаття '" + article.slug +
                    "': фото переприв'язано на " + article.image_path + "."
                );
            } catch (e) {
                log(
                    "[Рівень 2] Сторінка " + pagePlan.page + ", стаття '" + article.slug +
                    "': НЕ вдалося переприв'язати фото (" + e + ")."
                );
            }
        }

        log(
            "[Рівень 2] Сторінка " + pagePlan.page + ": заголовковий фрейм (id " + cluster.headline.item.id +
            ") <-> стаття '" + article.slug + "'."
        );

        var leadMember = findMemberByRole(cluster, "lead_intro");
        var bodyMember = findMemberByRole(cluster, "body");
        var minScale = plan.min_horizontal_scale || 97;

        var inserted = [];
        var skipped = [];
        var overset = [];

        if (cluster.headline.isComboHeadline) {
            // "Комбо"-кластер (див. COMBO_ELIGIBLE_ROLE): заголовок і тіло
            // статті живуть в ОДНІЙ історії одного фрейма, тому їх не можна
            // вставляти окремими викликами setFrameText (кожен виклик
            // затирає всю історію) -- натомість збираємо один об'єднаний
            // текст (заголовок [+ лід] + тіло) і вставляємо його одним
            // викликом, а індекси підзаголовків зсуваємо на кількість
            // абзаців, вставлених ПЕРЕД тілом.
            var comboLeadOffset = article.lead ? 1 : 0;
            var comboBodyText = article.lead ? (article.lead + "\n" + article.body) : article.body;
            var comboText = article.title + "\n" + comboBodyText;

            if (setFrameText(cluster.headline.item, comboText)) {
                inserted.push(article.lead ? "заголовок+лід+тіло (комбо)" : "заголовок+тіло (комбо)");
                if (!fitFrameText(cluster.headline.item, minScale)) {
                    overset.push("комбо");
                }
                applyHeadlineFontAlternation(cluster.headline.item, plan, i, pagePlan.page, article.slug);
                var comboShift = 1 + comboLeadOffset;
                var shiftedIndices = [];
                for (var si = 0; si < article.subheading_indices.length; si++) {
                    shiftedIndices.push(article.subheading_indices[si] + comboShift);
                }
                applySubheadingStyles(cluster.headline.item, shiftedIndices, subheadStyleName);
            } else {
                skipped.push("заголовок+тіло (комбо)");
            }
        } else {
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
                    applySubheadingStyles(bodyMember.item, article.subheading_indices, subheadStyleName);
                } else {
                    skipped.push("тіло");
                }
            }
        }

        log(
            "[Рівень 2] Сторінка " + pagePlan.page + ", стаття '" + article.slug + "': вставлено (" +
            (inserted.length > 0 ? inserted.join(", ") : "нічого") + "); пропущено без змін (" +
            (skipped.length > 0 ? skipped.join(", ") : "нічого") + ")."
        );

        if (overset.length > 0) {
            log(
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
        var proceed = confirm(
            "Попередження про шрифти:\n\n" + fontWarnings.join("\n") +
            "\n\nInDesign автоматично підмінить відсутні шрифти на схожі -- " +
            "текст переверстається, але видима гарнітура буде іншою (наприклад, " +
            "замість очікуваного шрифту з'явиться щось на кшталт \"Everest-Demi\").\n\n" +
            "Щоб виправити: покладіть файли цих шрифтів у папку \"Document Fonts\" " +
            "поруч із .indd-файлом цього випуску (InDesign підхопить їх автоматично, " +
            "без встановлення в систему), і запустіть скрипт знову.\n\n" +
            "Продовжити верстку попри це (OK) чи скасувати (Cancel)?",
            true
        );
        if (!proceed) {
            throw new Error("Скасовано користувачем через відсутні шрифти.");
        }
    }

    var meta = promptForIssueMeta();
    var doc = app.open(docFile);
    setRunningHeaderVariables(doc, meta.issueDate, meta.issueNumber);

    for (var i = 0; i < plan.pages.length; i++) {
        var pagePlan = plan.pages[i];
        if (pagePlan.status !== "planned" && pagePlan.status !== "planned_page1_special") {
            continue; // ручні/спеціальні/поза межами/порожні сторінки не чіпаємо
        }
        var page = doc.pages.item(pagePlan.page - 1);
        if (pagePlan.status === "planned_page1_special") {
            applyMifPage1Special(page, pagePlan, plan);
        } else {
            applyArticlesToPage(page, pagePlan, plan);
        }
    }

    if (SKIPPED_PAGES.length > 0) {
        log(
            "!!! УВАГА: " + SKIPPED_PAGES.length + " сторінк(а/и) ПРОПУЩЕНО без жодних змін " +
            "(стара стаття лишилась як є) -- " + SKIPPED_PAGES.join("; ") + ". " +
            "Причина завжди одна з двох: невідповідність кількості кластерів/статей, або " +
            "невідома роль абзацу -- див. деталі кластерів вище в цьому логу."
        );
    } else {
        log(
            "Усі заплановані сторінки (\"planned\"/\"planned_page1_special\") оброблено без " +
            "пропусків через невідповідність кластерів."
        );
    }

    log(
        "Готово (частково): preflight шрифтів, колонтитул, геометричне групування статей, " +
        "relink фото, вставка тексту заголовка/ліда/тіла, підтискання overset-тексту " +
        "(Horizontal Scale) та чергування шрифту заголовка (де підтверджено) виконано для " +
        "газет із розв'язаною мапою ролей (paragraph_style_roles або, як fallback, " +
        "character_size_roles); перевірка на реальному InDesign ще потрібна."
    );

    return RUN_LOG.join("\n");
}

main();
