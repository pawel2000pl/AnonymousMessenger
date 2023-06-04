
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
    const urlParams = new URLSearchParams();
    urlParams.append('languages', navigator.languages.join(";"));
    const result = await fetch("/query/get_translations?"+urlParams.toString());
    dataLanguage = await result.json();
};

var translatorPromise = init().then(translateAll);