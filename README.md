# RubyscoreVoteSpamer

## Pythonの仮想環境の構築

```
stardust✨stardust:~/RubyscoreVoteSpamer$ pyenv local 3.13.7
stardust✨stardust:~/RubyscoreVoteSpamer$ python3 -m venv .venv
stardust✨stardust:~/RubyscoreVoteSpamer$ source .venv/bin/activate
(.venv) stardust✨stardust:~/RubyscoreVoteSpamer$ python -V
Python 3.13.7
```

## 必要なPythonモジュールを導入する

```
(.venv) stardust✨stardust:~/RubyscoreVoteSpamer$ pip install Web3 dotenv
```

## Pythonモジュールのリスト取得と導入

```
pip install -r requirements.txt           # 入れる
pip freeze > requirements.txt             # 固定化して保存
```

## 実行

```
(.venv) stardust✨stardust:~/RubyscoreVoteSpamer$ python RubyscoreVoteSpammer.py 
```

