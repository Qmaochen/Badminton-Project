import streamlit as st
import random
import pandas as pd
import streamlit.components.v1 as components  # <--- 1. 改用這個內建元件

# ==========================================
# 0. 防睡功能 (免安裝套件版)
# ==========================================
def keep_awake():
    # 這是直接注入 JavaScript，請求瀏覽器保持螢幕開啟
    keep_awake_js = """
    <script>
    async function getWakeLock() {
        try {
            const wakeLock = await navigator.wakeLock.request('screen');
            console.log('Wake Lock is active!');
        } catch (err) {
            console.log(`${err.name}, ${err.message}`);
        }
    }
    // 網頁載入時執行
    getWakeLock();
    // 當使用者切換分頁回來時，再次執行
    document.addEventListener('visibilitychange', async () => {
        if (document.visibilityState === 'visible') {
            getWakeLock();
        }
    });
    </script>
    """
    components.html(keep_awake_js, height=0, width=0)

# ==========================================
# 1. 核心邏輯區
# ==========================================

class BadmintonManager:
    def __init__(self):
        self.players = []
        self.courts_num = 2
        
        # 數據統計
        self.play_counts = {}       
        self.consecutive_rests = {} 
        
        self.partner_history = {}   
        self.opponent_history = {}  
        self.match_history = []     
        
        # 場地狀態
        self.courts_status = {}  
        self.busy_players = set()   
        
        self._init_courts()

    def _init_courts(self):
        for i in range(1, self.courts_num + 1):
            if i not in self.courts_status:
                self.courts_status[i] = None

    def add_player(self, name):
        name = name.strip()
        if not name:
            return False, "名字不能為空"
        if name in self.players:
            return False, f"{name} 已經在名單內了"
        
        self.players.append(name)
        self.play_counts[name] = 0
        self.consecutive_rests[name] = 0
        return True, f"已加入球員: {name}"

    def remove_player(self, name):
        if name not in self.players:
            return False, "找不到此球員"
        
        if name in self.busy_players:
            return False, f"⚠️ {name} 正在場上比賽中，請先結算該場比賽後再移除。"

        self.players.remove(name)
        if name in self.consecutive_rests:
            del self.consecutive_rests[name]

        return True, f"已將 {name} 移出名單 (歷史戰績保留)"

    def update_courts_num(self, num):
        if num < 1: return
        if num > self.courts_num:
            for i in range(self.courts_num + 1, num + 1):
                self.courts_status[i] = None
        self.courts_num = num

    def get_pair_cost(self, p1, p2):
        key = tuple(sorted((p1, p2)))
        return self.partner_history.get(key, 0)

    def get_opponent_cost(self, p1, p2):
        key = tuple(sorted((p1, p2)))
        return self.opponent_history.get(key, 0)

    def get_available_players(self):
        return [p for p in self.players if p not in self.busy_players]

    def fill_empty_courts(self):
        logs = []
        empty_courts = [
            cid for cid in range(1, self.courts_num + 1)
            if self.courts_status.get(cid) is None
        ]
        
        if not empty_courts:
            return ["沒有空場地需要填補。"]

        for cid in empty_courts:
            available = self.get_available_players()
            
            if len(available) < 4:
                logs.append(f"⚠️ 球場 {cid}: 剩餘人數不足 ({len(available)}人)，暫時閒置。")
                continue

            random.shuffle(available)
            available.sort(key=lambda x: (-self.consecutive_rests.get(x, 0), self.play_counts.get(x, 0)))
            
            group = available[:4]
            
            best_combo = None
            min_cost = float('inf')
            
            combos = [
                ((group[0], group[1]), (group[2], group[3])),
                ((group[0], group[2]), (group[1], group[3])),
                ((group[0], group[3]), (group[1], group[2]))
            ]
            
            for t1, t2 in combos:
                p_cost = self.get_pair_cost(*t1) + self.get_pair_cost(*t2)
                
                o_cost = 0
                for p_a in t1:
                    for p_b in t2:
                        o_cost += self.get_opponent_cost(p_a, p_b)
                
                total_cost = (p_cost * 1000) + o_cost
                
                if total_cost < min_cost:
                    min_cost = total_cost
                    best_combo = (t1, t2)
            
            team1, team2 = best_combo
            
            self.courts_status[cid] = {'team1': team1, 'team2': team2, 'players': group}
            for p in group:
                self.busy_players.add(p)
                self.play_counts[p] += 1
            
            logs.append(f"✅ 球場 {cid}: {team1[0]}&{team1[1]} vs {team2[0]}&{team2[1]}")
        
        for p in self.players:
            if p in self.busy_players:
                self.consecutive_rests[p] = 0
            else:
                self.consecutive_rests[p] = self.consecutive_rests.get(p, 0) + 1
            
        return logs

    def finish_match(self, court_id, score_str):
        match = self.courts_status.get(court_id)
        if not match:
            return False

        t1, t2 = match['team1'], match['team2']
        
        self.match_history.append({
            'team1': f"{t1[0]}&{t1[1]}", 
            'team2': f"{t2[0]}&{t2[1]}", 
            'score': score_str if score_str else "無紀錄"
        })
        
        key1 = tuple(sorted(t1))
        key2 = tuple(sorted(t2))
        self.partner_history[key1] = self.partner_history.get(key1, 0) + 1
        self.partner_history[key2] = self.partner_history.get(key2, 0) + 1
        
        for p_a in t1:
            for p_b in t2:
                key_opp = tuple(sorted((p_a, p_b)))
                self.opponent_history[key_opp] = self.opponent_history.get(key_opp, 0) + 1
        
        for p in match['players']:
            self.busy_players.discard(p)
        
        self.courts_status[court_id] = None
        return True

    def export_data(self):
        if self.match_history:
            df_history = pd.DataFrame(self.match_history)
            df_history.columns = ['隊伍A', '隊伍B', '比分']
        else:
            df_history = pd.DataFrame(columns=['隊伍A', '隊伍B', '比分'])

        if self.play_counts:
            data = []
            for name, count in self.play_counts.items():
                status_suffix = " (已離)" if name not in self.players else ""
                data.append({
                    "姓名": name + status_suffix, 
                    "上場次數": count, 
                    "目前連休": self.consecutive_rests.get(name, "-") 
                })
            df_stats = pd.DataFrame(data)
            df_stats = df_stats.sort_values(by="上場次數", ascending=False)
        else:
            df_stats = pd.DataFrame(columns=['姓名', '上場次數', '目前連休'])

        return df_history, df_stats

    def generate_text_report(self):
        if not self.match_history:
            return "尚無比賽紀錄"
        
        report = "🏸 今日羽球戰報 🏸\n"
        report += "="*20 + "\n"
        for i, match in enumerate(self.match_history, 1):
            report += f"{i}. {match['team1']} vs {match['team2']} ({match['score']})\n"
        
        report += "\n📊 上場統計:\n"
        sorted_counts = sorted(self.play_counts.items(), key=lambda x: x[1], reverse=True)
        for name, count in sorted_counts:
            suffix = "(已離)" if name not in self.players else ""
            report += f"{name}{suffix}: {count}場\n"
            
        return report

# ==========================================
# 2. Streamlit 介面區
# ==========================================

st.set_page_config(page_title="羽球排點系統", page_icon="🏸", layout="wide")

# 呼叫防睡函式 (這會隱藏在背景執行)
keep_awake()

if 'manager' not in st.session_state:
    st.session_state.manager = BadmintonManager()

mgr = st.session_state.manager

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定與管理")
    
    new_court_num = st.number_input("球場數量", min_value=1, max_value=20, value=mgr.courts_num)
    if new_court_num != mgr.courts_num:
        mgr.update_courts_num(new_court_num)
        st.success(f"已更改為 {new_court_num} 個球場")

    st.divider()

    st.subheader("➕ 新增球員")
    with st.form("add_player_form", clear_on_submit=True):
        new_name = st.text_input("輸入名字")
        submitted = st.form_submit_button("加入")
        if submitted:
            success, msg = mgr.add_player(new_name)
            if success:
                st.success(msg)
            else:
                st.error(msg)
    
    st.divider()

    st.subheader("🗑️ 移除球員 (提早離開)")
    if mgr.players:
        player_to_remove = st.selectbox("選擇要移除的球員", mgr.players, key="remove_select")
        if st.button("確認移除", type="secondary"):
            success, msg = mgr.remove_player(player_to_remove)
            if success:
                st.success(msg)
                st.rerun() 
            else:
                st.error(msg)
    else:
        st.caption("目前無球員可移除")
    
    st.divider()

    st.subheader("📊 上場統計")
    st.caption("連休 = 目前連續休息幾場")
    if mgr.play_counts:
        _, df_stats = mgr.export_data()
        df_stats = df_stats.sort_values(by=['目前連休', '上場次數'], ascending=[False, True])
        st.dataframe(df_stats, hide_index=True, use_container_width=True)
    else:
        st.text("尚無球員資料")

    st.divider()
    st.header("💾 資料存檔")
    
    df_history, df_stats = mgr.export_data()
    
    csv_history = df_history.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下載對戰紀錄 (CSV)",
        data=csv_history,
        file_name='badminton_match_history.csv',
        mime='text/csv',
    )
    
    csv_stats = df_stats.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下載個人統計 (CSV)",
        data=csv_stats,
        file_name='badminton_player_stats.csv',
        mime='text/csv',
    )
    
    with st.expander("📋 複製文字戰報"):
        st.text_area("內容", mgr.generate_text_report(), height=250)

# --- 主畫面 ---
st.title("🏸 羽球排點系統")

col_action, col_info = st.columns([2, 1])
with col_action:
    st.write("#### 👇 下一輪安排")
    if st.button("🎲 一鍵補人 / 洗牌 (Next)", type="primary", use_container_width=True):
        logs = mgr.fill_empty_courts()
        for log in logs:
            if "⚠️" in log:
                st.warning(log)
            else:
                st.success(log)

with col_info:
    available = mgr.get_available_players()
    st.metric(label="等待人數", value=f"{len(available)} 人")

st.divider()
st.subheader("🏟️ 球場狀態")

max_court_id = mgr.courts_num
if mgr.courts_status:
    max_court_id = max(max_court_id, max(mgr.courts_status.keys()))

cols = st.columns(mgr.courts_num)

for i in range(1, max_court_id + 1):
    status = mgr.courts_status.get(i)
    if i > mgr.courts_num and status is None:
        continue

    if i <= mgr.courts_num:
        container = cols[i-1].container(border=True)
    else:
        container = st.container(border=True)
    
    court_title = f"球場 {i}"
    if i > mgr.courts_num:
        court_title += " (即將關閉)"
        
    container.markdown(f"### {court_title}")

    if status:
        t1 = status['team1']
        t2 = status['team2']
        container.markdown(f"🔴 **{t1[0]} & {t1[1]}**")
        container.markdown(f"🔵 **{t2[0]} & {t2[1]}**")
        container.markdown("---")
        
        with container.popover("🏁 結束比賽"):
            score_input = st.text_input("輸入比分 (選填)", key=f"score_{i}")
            if st.button("確認結算", key=f"btn_fin_{i}"):
                mgr.finish_match(i, score_input)
                st.rerun()
    else:
        container.success("🟩 閒置中")
        container.caption("等待分配...")

st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("⏳ 等待名單")
    if available:
        wait_list_display = []
        for p in available:
            rest_count = mgr.consecutive_rests.get(p, 0)
            if rest_count > 0:
                wait_list_display.append(f"`{p}(休{rest_count})`")
            else:
                wait_list_display.append(f"`{p}`")
        
        st.markdown(" ".join(wait_list_display))
        st.caption("註：(休N) 代表已連續休息 N 場，數字越大越優先上場")
    else:
        st.caption("無")

with c2:
    st.subheader("📜 近期戰績")
    if mgr.match_history:
        history_df = pd.DataFrame(mgr.match_history)
        history_df.columns = ['隊伍 A', '隊伍 B', '比分']
        st.dataframe(history_df.tail(5).iloc[::-1], hide_index=True)
    else:
        st.caption("尚無紀錄")