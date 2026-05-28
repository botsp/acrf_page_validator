
28May2026T7:41PM
Issue1.RawTexts 应该是要存储从box抓取到的文本对吧？如果要是多个box，那采用|进行分隔，但要确保完整的box内容；可是你现在解析的结果是这样的

| Variable   | Pages     | PageCount | Category           | Flag                   | RawTexts                                                                 |
|------------|-----------|-----------|--------------------|------------------------|--------------------------------------------------------------------------|
| ACNDD      | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNDD in SUPPAE...                                                       |
| ACNDNC     | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNDNC in SUPPAE...                                                      |
| ACNDW      | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNDW in SUPPAE...                                                       |
| ACNNA      | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNNA in SUPPAE...                                                       |
| AE         | 2,3,4,17  | 4         | standard_variable   | suffix_prefix_match    | AE (Adverse Events) \| General Cause of Death #1 AE (Adverse Events) DDSPID= DDORRE \| AE and CM \| Use... |
| AEACN      | 3         | 1         | standard_variable   | suffix_prefix_match    | If multiple values are selected AEACN=MULTIPLE...                        |
| AEDIS      | 3         | 1         | standard_variable   | suffix_prefix_match    | AEDIS in SUPPAE...                                                       |
| AEDISCDT   | 4         | 1         | standard_variable   | suffix_prefix_match    | AEDISCDT in SUPPAE...                                                     |
| AEENDTC    | 2         | 1         | standard_variable   | suffix_prefix_match    | AEENDTC...                                                               |




