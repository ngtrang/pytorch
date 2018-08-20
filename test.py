from pyvi import ViTokenizer
str ="Chào Sarah, bạn khỏe không?"
lst = ViTokenizer.tokenize(str).split(" ")
print(lst)