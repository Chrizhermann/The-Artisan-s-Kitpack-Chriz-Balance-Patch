BEGIN C0FS#06

CHAIN IF WEIGHT #-1 ~True()~ THEN C0FS#06 miracle
~You feel the attention of your deity focused upon you. With a word, you may call upon a particular boon to aid you.~
END
IF ~CheckStatLT(LastTalkedToBy,10,CHR)~ DO ~SetupWish(4,4)~ + miracle1
IF ~CheckStatGT(LastTalkedToBy,9,CHR)
    CheckStatLT(LastTalkedToBy,18,CHR)~ DO ~SetupWish(4,3)~ + miracle2
IF ~CheckStatGT(LastTalkedToBy,17,CHR)
    CheckStatLT(LastTalkedToBy,23,CHR)~ DO ~SetupWish(4,2)~ + miracle3
IF ~CheckStatGT(LastTalkedToBy,22,CHR)~ DO ~SetupWish(4,1)~ + miracle4

CHAIN C0FS#06 miracle1
~Your lack of confidence makes you doubt whether your deity will even display their favor in a beneficial way to you.~
EXTERN C0FS#06 miracle5

CHAIN C0FS#06 miracle2
~Your devotion to your god makes you reasonably assured that whatever you receive will be of some benefit, though whether it will be enough to make a difference is uncertain.~
EXTERN C0FS#06 miracle5

CHAIN C0FS#06 miracle3
~You are confident that you will be able to persuade your deity into giving you something of significant value. That said, you can never be too certain with such things.~
EXTERN C0FS#06 miracle5

CHAIN C0FS#06 miracle4
~Your overwhelming force of personality makes you assured that your deity will be particularly generous to you with their gifts, even if may not be exactly what you want.~
EXTERN C0FS#06 miracle5

CHAIN C0FS#06 miracle5
~Regardless, the petition has been made, and you will have to accept the result. What will you choose?~
COPY_TRANS WISH25 12