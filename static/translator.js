
var dataLanguage = {};

const translate = function(text) {
    if (dataLanguage[text])
        return dataLanguage[text];
    return text;
};

const translateAll = function() {
    const keys = ['innerText', 'value', 'textContent'];
    var applyTrans = [];
    Array.from(document.getElementsByClassName("translatable")).forEach((element)=>{
        keys.forEach((key)=>{
            if (element[key] && element[key] != "") {
                const originalKey = 'original_text_'+key;
                if (!element[originalKey])
                    element[originalKey] = element[key];
                applyTrans.push(()=>{
                    element[key] = translate(element[originalKey]);
                });
            }
        });
    });
    applyTrans.forEach((fun)=>{fun();});
};

const fetchLanguages = async function(languages=['en']) {
    const urlParams = new URLSearchParams();
    urlParams.append('languages', languages.join(";"));
    const result = await fetch("/query/get_translations?"+urlParams.toString());
    dataLanguage = await result.json();
};

const switchLanguage = async function(newLanguage) {
    let newLanguageArray = [];
    if (newLanguage.length > 0) {
        localStorage.selectedLanguage = newLanguage;
        newLanguageArray = [newLanguage];
    }
    await fetchLanguages(newLanguageArray.concat(navigator.languages));
    translateAll();
};

const init = async function() {
    await switchLanguage(localStorage.selectedLanguage??'');
    const langList = dataLanguage.__supported_languages__;
    Array.from(document.getElementsByClassName('language-selector')).forEach((element)=>{
        element.innerHTML = '';

        let summary = document.createElement('summary');
        summary.textContent = dataLanguage.__language_name__;
        summary.onblur = ()=>{setTimeout(()=>{element.open = '';}, 250);};
        element.appendChild(summary);

        langList.forEach((lang)=>{
            let option = document.createElement('div');
            option.textContent = lang;
            option.onclick = ()=>{
                switchLanguage(lang).then(()=>{element.open = '';});
                summary.textContent = lang;
            };
            element.append(option);
        });
    });
};

var translatorPromise = init();