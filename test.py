#Creat dataset
#dia =""
#with open("data/anwser_databse.txt", "a",encoding="utf-8") as text_file:
#Add vietnamse text
# with open("data/vi_database.txt", "a",encoding="utf-8") as text_file:
#   while dia != "exit":
#     dia = input("input text: ")
#     text_file.write(dia+"\n")
# text_file.close()

#Pre-processing 100 conversation of eng-viet
lines = open("data/100eng-vie.txt","r",encoding='utf-8').read().split('\n')
lines = list(filter(None,lines))
lines.append("")
index=[]
for i in range(0,len(lines)):
  if u"Bài học" in lines[i]:
    index.append(i)
index.append(len(lines))

vilst = []
y = 0
flag = False
for x in  index:
  tmp = []

  while y < x :
    if y == 2920:
      flag = True
    if y  < len(lines)-1:
      if u'Bài học' in lines[y+1]:
       tmp.append("")
      else:
        if y+2 < len(lines):
          if ":" in lines[y+2]:
            str = lines[y+2].split(":")
            tmp.append(str[1])
          else:
            tmp.append(lines[y+2])
    y +=2
  y = x
  vilst.append(tmp)


# chuyen vilst thanh cac cap hoi thoai va in vao text

with open('100conver.txt','w',encoding='utf-8') as file:
  for sublst in vilst:
    for x in range(0, len(sublst)-1):
      if x % 2 == 0:
        str = "\\".join([sublst[x], sublst[x + 1]])
        file.write(str +'\n')
file.close()
