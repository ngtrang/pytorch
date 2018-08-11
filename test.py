MAX_LENGTH = 3

def filterPair(p):
    # if not p:
    #     return False
    # else:
    #     return  len(p[0].split(' ')) < MAX_LENGTH and len(p[1].split(' ')) < MAX_LENGTH
    lst = [x for x in p if len(x.split(' ')) < MAX_LENGTH ]
    if len(lst)== 2:
        return True
    else:
        return False


def filterPairs(pairs):
    #tmp =[pair for pair in pairs if filterPair(pair)]
    #lst = filter(lambda pair: filterPair(pair), pairs)
    return [pair for pair in pairs if filterPair(pair)]

pairs = [['привет', 'приветос ! как тебя зовут ?'],
[' привет', ''],
[' ', ''],
[' привет', 'и тебе привет !'],
[' привет', 'привет ! кажется мы не знакомы ?'],]
pairs = filterPairs(pairs)
print(pairs)