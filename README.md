# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/brokenpip3/lotb/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                               |    Stmts |     Miss |   Cover |   Missing |
|----------------------------------- | -------: | -------: | ------: | --------: |
| lotb/common/config.py              |       33 |        0 |    100% |           |
| lotb/common/plugin\_class.py       |      145 |        6 |     96% |109, 142, 196, 198-199, 202 |
| lotb/common/version.py             |        2 |        2 |      0% |       1-3 |
| lotb/lotb.py                       |      162 |       79 |     51% |31-51, 58-59, 76-78, 82-84, 88-90, 120-130, 145-150, 161-170, 174-212, 216 |
| lotb/plugins/assistant.py          |      396 |       81 |     80% |45, 58-61, 165-170, 174-192, 196-209, 215-225, 248-252, 258-261, 271-279, 285-290, 326-332, 343, 346-353, 428-431, 539, 576, 579-580, 613-614 |
| lotb/plugins/image.py              |      179 |       13 |     93% |36-39, 98-99, 115-116, 143-146, 208-209 |
| lotb/plugins/llm.py                |       69 |       11 |     84% |58-59, 63, 65, 72, 109-111, 119-120, 155 |
| lotb/plugins/memo.py               |       83 |       14 |     83% |63, 85-86, 89-90, 125-128, 134-135, 143-144, 156 |
| lotb/plugins/notes.py              |       64 |       12 |     81% |30-31, 40-41, 47-48, 60-61, 81-82, 87, 104 |
| lotb/plugins/prometheus\_alerts.py |       95 |       16 |     83% |23, 40-42, 81-82, 88-89, 110, 114-119, 141-142 |
| lotb/plugins/quote.py              |       77 |        2 |     97% |   118-120 |
| lotb/plugins/readwise.py           |       50 |        4 |     92% |     55-59 |
| lotb/plugins/remindme.py           |       92 |       12 |     87% |40-43, 62-63, 69-76, 129-130, 163-164, 173 |
| lotb/plugins/rssfeed.py            |       60 |       10 |     83% |22, 24, 30, 71-73, 76-81, 87 |
| lotb/plugins/socialfix.py          |       37 |        0 |    100% |           |
| lotb/plugins/welcome.py            |       17 |        0 |    100% |           |
|                          **TOTAL** | **1561** |  **262** | **83%** |           |

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