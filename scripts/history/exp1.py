# NOTE: guideline, not an exact or supported tool. Written for one keyboard (Rapoo V720) during research;
# paths, offsets and assumptions may need adjusting. No firmware images are shipped with this repository.
import sys
sys.path.insert(0,".")
from tick_sim import *
img=open("../patch/v720_stream4.bin","rb").read()
c=FW(img[:0xF000]+bytes(0x1000)); c.pc=0
n=0
while c.pc!=0x5C32 and n<3_000_000: c.step(); n+=1
def tick(c,cap=1_500_000):
    c.iram[0x2B]=1; k=0; heads=0
    while k<cap:
        c.step(); k+=1
        if c.pc==0x5C32:
            break
    return k
for t in range(8): tick(c)
print("steady: 0512=%02x 20.1=%d 20.2=%d"%(c.xram[0x512],c.bget(0x01),c.bget(0x02)))
lv0=live(c)
for t in range(3):
    tick(c); print("tick",t,"live changed vs steady:",live(c)!=lv0)
# now deliver tagged frame: green plane (offset 0x84)=0xFF for all keys, others 0
st=bytearray(0x400); 
for i in range(0x84): st[0x84+i]=0xFF   # plane index1
st[0x318:0x31C]=b"RTV2"
c.xram[0x05D1:0x05D1+0x400]=st
# CASE A: no flags at all
for t in range(4): tick(c)
lvA=live(c); print("A (no flags): live changed:",lvA!=lv0, "green bytes:",sum(1 for i in range(1,len(lvA),3) if lvA[i]==0xFF))
# CASE B: v4 flags (20.1, 27.1)
c.bset(0x01,1); c.bset(0x39,1)
hist=[]
for t in range(6):
    tick(c); l=live(c); hist.append((sum(1 for i in range(1,len(l),3) if l[i]),c.xram[0x512],c.bget(0x01),c.bget(0x02)))
print("B (20.1,27.1):",hist)
def grid(l):
    for r in range(6):
        print(" ".join("%02x%02x%02x"%tuple(l[r*0x42+k*3:r*0x42+k*3+3]) for k in range(22)))
print("steady live (before frame):"); grid(lv0)
print("after frame B:"); grid(live(c))
