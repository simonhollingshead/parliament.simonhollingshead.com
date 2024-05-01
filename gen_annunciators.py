import minify_html
from string import Template
from os import path

class NoDollarTemplate(Template):
    delimiter = '_tpl_'

commons = {"filename": "out/commons.htm",
           "house_lower": "commons",
           "house_precap": "Commons",
           "house_allcap": "COMMONS",
           "house_id": 0,
           "house_hex": "#005434",
           "scroll_hex": "#9D0830"}

lords = {"filename": "out/lords.htm",
         "house_lower": "lords",
         "house_precap": "Lords",
         "house_allcap": "LORDS",
         "house_id": 1,
         "house_hex": "#9D0830",
         "scroll_hex": "#005434"}

with open(path.join(path.dirname(__file__), "template.htm"), "r") as f:
    body = NoDollarTemplate(f.read())

for params in [commons, lords]:
    with open(path.join(path.dirname(__file__), params["filename"]), "w") as f:
        f.write(body.substitute(params))
        # f.write(minify_html.minify(body.substitute(params), minify_css=True, minify_js=True))
