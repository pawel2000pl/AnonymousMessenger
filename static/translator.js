
var dataLanguage = {};

const translate = function(text) {
    if (dataLanguage[text])
        return dataLanguage[text];
    return text;
}

const translateAll = function() {
    const translatable = document.getElementsByClassName("translatable");
    for (let i=0;i<translatable.length;i++) {
        if (translatable[i].innerText != "")
            translatable[i].innerText = translate(translatable[i].innerText);        
        if (translatable[i].value != "")
            translatable[i].value = translate(translatable[i].value);
    }
};

const init = async function() {
    const result = await fetch("/translates.json");
    const data = await result.json();
    dataLanguage = data[navigator.language]??{};
};

var translatorPromise = init().then(translateAll);