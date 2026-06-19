'use strict';
const SaveManager = {
  _k: { hs:'piyo_hs', hw:'piyo_hw', bgm:'piyo_bgm', se:'piyo_se' },
  getHigh()    { return { score: +localStorage.getItem(this._k.hs)||0, wave: +localStorage.getItem(this._k.hw)||0 }; },
  getBgm()     { const v=localStorage.getItem(this._k.bgm); return v===null?true:v==='true'; },
  getSe()      { const v=localStorage.getItem(this._k.se);  return v===null?true:v==='true'; },
  setBgm(v)    { localStorage.setItem(this._k.bgm, String(v)); },
  setSe(v)     { localStorage.setItem(this._k.se,  String(v)); },
  save(score, wave) {
    const h=this.getHigh();
    const isHS=score>h.score;
    if (isHS)        localStorage.setItem(this._k.hs, score);
    if (wave>h.wave) localStorage.setItem(this._k.hw, wave);
    return isHS;
  }
};
