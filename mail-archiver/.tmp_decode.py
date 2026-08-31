# -*- coding: utf-8 -*-
body = open('/Users/apple/mail-archiver/.tmp_body.txt', encoding='utf-8').read()
b = body.encode('cp1252', errors='replace')
for enc in ('gbk', 'euc_jp'):
    print('=====', enc)
    print(b.decode(enc, errors='replace'))
