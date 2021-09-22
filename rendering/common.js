function outerHeight(element) {
    // get the entire height an element takes up, the "outer height"
    const height = element.offsetHeight,
        style = window.getComputedStyle(element)

    return ['top', 'bottom']
        .map(side => parseInt(style[`margin-${side}`]))
        .reduce((total, side) => total + side, height)
}

function fit(elemid) {
    // fit the child of elemid inside elemid by downsizing the font size of elemid's child
    // rewrite of https://stackoverflow.com/a/6112914/9044183
    let elem = document.getElementById(elemid)
    let elemc = elem.children[0]
    while (outerHeight(elem) < outerHeight(elemc)) {
        // https://stackoverflow.com/a/15195345/9044183
        let style = window.getComputedStyle(elemc, null).getPropertyValue('font-size');
        let fontSize = parseFloat(style);
        console.log(fontSize)
        if (fontSize === 0) { // last resort to prevent infinite loops
            break;
        }
        elemc.style.fontSize = (fontSize - 1) + 'px';
    }
}


function roundToPlace(num, place) {
    // round num to place places
    let m = Number((Math.abs(num) * 10 ** place).toPrecision(15));
    return Math.round(m) / 10 ** place * Math.sign(num);
}

function calculateStrokeTextCSS(steps) {
    // http://www.coding-dude.com/wp/css/css-stroke-text/
    // places an arbitrarily high amount of shadows around elem to simulate border.
    let css = [];
    for (let i = 0; i < steps; i++) {
        let angle = (i * 2 * Math.PI) / steps;
        let cos = roundToPlace(Math.cos(angle), 4)
        let sin = roundToPlace(Math.sin(angle), 4)
        css.push(`calc(var(--stroke-width) * ${cos}) calc(var(--stroke-width) * ${sin}) 0 var(--stroke-color)`)
    }

    return css.join(",\n");
}

function abbrNumber(str) {
    // abbreveate number with SI scale (i.e. 1000=1K, 1000000=1M, etc)
    let n = Number(str);
    if (n < 1e3) return n;
    if (n >= 1e3 && n < 1e6) return +(n / 1e3).toFixed(1) + "K";
    if (n >= 1e6 && n < 1e9) return +(n / 1e6).toFixed(1) + "M";
    if (n >= 1e9 && n < 1e12) return +(n / 1e9).toFixed(1) + "B";
}

function randint(min, max) {
    // get a random int between min and max
    return Math.floor(Math.random() * (max - min)) + min;
}

function randfloat(min, max) {
    // get a random float between min and max
    return Math.random() * (max - min) + min
}

// parse emojis to twemoji
twemoji.parse(document.body);
