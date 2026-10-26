# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/brokenpip3/lotb/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------ | -------: | -------: | ------: | --------: |
| lotb/common/commands.py             |        9 |        0 |    100% |           |
| lotb/common/config.py               |       33 |        0 |    100% |           |
| lotb/common/plugin\_class.py        |      157 |        2 |     99% |     69-70 |
| lotb/common/tools.py                |       59 |        4 |     93% | 63, 95-97 |
| lotb/common/version.py              |        2 |        2 |      0% |       1-3 |
| lotb/lotb.py                        |      196 |       14 |     93% |60-61, 70-71, 75-76, 118-122, 224-225, 255 |
| lotb/plugins/\_llm/\_\_init\_\_.py  |        5 |        0 |    100% |           |
| lotb/plugins/\_llm/assistant.py     |      239 |       28 |     88% |53, 56, 62-63, 116-122, 138, 141-148, 168, 181, 198, 242, 253, 342, 345-346, 350-351 |
| lotb/plugins/\_llm/config.py        |       31 |        2 |     94% |    28, 30 |
| lotb/plugins/\_llm/history.py       |       28 |        3 |     89% |34, 67, 71 |
| lotb/plugins/\_llm/mcp\_manager.py  |       97 |       13 |     87% |28, 69-74, 119-123, 129-132 |
| lotb/plugins/\_llm/prompts.py       |       11 |        0 |    100% |           |
| lotb/plugins/\_llm/simple.py        |       75 |       11 |     85% |35, 38, 51-52, 87, 98-100, 103-105 |
| lotb/plugins/\_llm/tool\_handler.py |      102 |       12 |     88% |39, 60, 64-66, 71-74, 80-82, 111, 143 |
| lotb/plugins/image.py               |      183 |       11 |     94% |38-41, 99-100, 136, 144, 160, 238-239 |
| lotb/plugins/llm.py                 |       33 |        5 |     85% |24-25, 47-49 |
| lotb/plugins/memo.py                |       89 |       10 |     89% |65, 136-139, 145-146, 154-155, 167 |
| lotb/plugins/notes.py               |       65 |        8 |     88% |47, 53, 55, 63, 91-92, 97, 114 |
| lotb/plugins/prometheus\_alerts.py  |       95 |       16 |     83% |23, 40-42, 81-82, 88-89, 110, 114-119, 141-142 |
| lotb/plugins/quote.py               |       84 |        3 |     96% |78, 139-141 |
| lotb/plugins/readwise.py            |       54 |        4 |     93% |     69-73 |
| lotb/plugins/remindme.py            |      106 |       10 |     91% |56-59, 81, 85, 87, 147-148, 184-185, 194 |
| lotb/plugins/rssfeed.py             |       60 |       10 |     83% |22, 24, 30, 71-73, 76-81, 87 |
| lotb/plugins/socialfix.py           |       51 |        3 |     94% | 71, 78-79 |
| lotb/plugins/tickets18.py           |      286 |       11 |     96% |76, 201, 238, 241-242, 244, 261, 276, 289, 314, 319 |
| lotb/plugins/welcome.py             |       22 |        0 |    100% |           |
| **TOTAL**                           | **2172** |  **182** | **92%** |           |

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