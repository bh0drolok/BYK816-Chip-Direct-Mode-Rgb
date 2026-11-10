#include "KeyboardLayoutManager.h"
#include <cstdio>
int main(){
  KeyboardLayoutManager kb(KEYBOARD_LAYOUT_ANSI_QWERTY, KEYBOARD_SIZE_FULL);
  printf("rows %u cols %u keys %u\n", kb.GetRowCount(), kb.GetColumnCount(), kb.GetKeyCount());
  matrix_map_type m = kb.GetKeyMap(KEYBOARD_MAP_FILL_TYPE_COUNT);
  for(unsigned r=0;r<m.height;r++){ for(unsigned c=0;c<m.width;c++){ unsigned v=m.map[r*m.width+c]; if(v==0xFFFFFFFF) printf("  . "); else printf("%3u ",v);} printf("\n"); }
  for(unsigned i=0;i<kb.GetKeyCount();i++) printf("%u:%s ", i, kb.GetKeyNameAt(i).c_str());
  printf("\n");
}
#include "LogManager.h"
LogManager* LogManager::get(){ static LogManager* p=nullptr; return p; }
void LogManager::LogEntry(const char*,int,unsigned int,const char*,...){}
