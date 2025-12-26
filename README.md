# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/brokenpip3/lotb/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------ | -------: | -------: | ------: | --------: |
| lotb/common/config.py               |       33 |        0 |    100% |           |
| lotb/common/plugin\_class.py        |      149 |        2 |     99% |     65-66 |
| lotb/common/version.py              |        2 |        2 |      0% |       1-3 |
| lotb/lotb.py                        |      169 |       16 |     91% |58-59, 66-67, 84-86, 90-92, 96-98, 193-194, 224 |
| lotb/plugins/\_llm/\_\_init\_\_.py  |        5 |        0 |    100% |           |
| lotb/plugins/\_llm/assistant.py     |      194 |       33 |     83% |49-62, 107-113, 124, 127-134, 148, 159, 162, 275, 278, 281-282, 286-287 |
| lotb/plugins/\_llm/config.py        |       33 |        2 |     94% |    31, 33 |
| lotb/plugins/\_llm/history.py       |       28 |        3 |     89% |34, 67, 71 |
| lotb/plugins/\_llm/mcp\_manager.py  |       97 |       13 |     87% |28, 69-74, 119-123, 129-132 |
| lotb/plugins/\_llm/prompts.py       |       11 |        0 |    100% |           |
| lotb/plugins/\_llm/simple.py        |       71 |       11 |     85% |35, 38, 51-52, 82, 93-95, 98-100 |
| lotb/plugins/\_llm/tool\_handler.py |      102 |       12 |     88% |39, 60, 64-66, 71-74, 80-82, 111, 143 |
| lotb/plugins/image.py               |      179 |       13 |     93% |36-39, 98-99, 115-116, 143-146, 208-209 |
| lotb/plugins/llm.py                 |       33 |        5 |     85% |24-25, 47-49 |
| lotb/plugins/memo.py                |       83 |       14 |     83% |63, 85-86, 89-90, 125-128, 134-135, 143-144, 156 |
| lotb/plugins/notes.py               |       64 |       12 |     81% |30-31, 40-41, 47-48, 60-61, 81-82, 87, 104 |
| lotb/plugins/prometheus\_alerts.py  |       95 |       16 |     83% |23, 40-42, 81-82, 88-89, 110, 114-119, 141-142 |
| lotb/plugins/quote.py               |       77 |        2 |     97% |   118-120 |
| lotb/plugins/readwise.py            |       50 |        4 |     92% |     55-59 |
| lotb/plugins/remindme.py            |       92 |       12 |     87% |40-43, 62-63, 69-76, 129-130, 163-164, 173 |
| lotb/plugins/rssfeed.py             |       60 |       10 |     83% |22, 24, 30, 71-73, 76-81, 87 |
| lotb/plugins/socialfix.py           |       37 |        0 |    100% |           |
| lotb/plugins/welcome.py             |       17 |        0 |    100% |           |
| **TOTAL**                           | **1681** |  **182** | **89%** |           |

3 empty files skipped.


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/brokenpip3/lotb/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/brokenpip3/lotb/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/brokenpip3/lotb/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/brokenpip3/lotb/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fbrokenpip3%2Flotb%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/brokenpip3/lotb/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.