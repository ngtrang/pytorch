#Creat dataset
dia =""
with open("data/anwser_databse.txt", "a",encoding="utf-8") as text_file:
  while dia != "exit":
    dia = input("input text: ")
    text_file.write(dia+"\n")
text_file.close()
