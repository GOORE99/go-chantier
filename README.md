# GO-CHANTIER

## environnement vituel
python3 -m venv .venv
.venv\Scripts\activate.bat
pip install Flask
pip freeze
cls

## flask
flask run
flask --app app/main.py run --debug


## git
git init
git status
git add .
git config --global user.email "kouakousergegoore@gmail.com"
git commit -m "Initial commit"
git remote add origin https://github.com/GOORE99/go-chantier.git
git branch
git push -u origin master

