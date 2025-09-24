"""
Mountain Viewer — PySide6

This update adds:
 - animated collapsible sidebar (smooth width animation + label hide)
 - restored polished UI style
 - Mountains page corrected: LEFT shows *full mountain information* (name, height, country, region, description, image placeholder), RIGHT shows *groups for that mountain* in chronological order (with leader shown)
 - Top center mountain combo still present; selecting a mountain updates Mountains page immediately

How to run:
  pip install PySide6
  python mountain_viewer_pyside6.py

Adjust BASE_URL to point to your API server.
"""

import sys
import json
from datetime import datetime
from PySide6.QtCore import Qt, QUrl, Slot, QDate, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QComboBox, QHBoxLayout, QVBoxLayout,
    QTextEdit, QListWidget, QListWidgetItem, QFrame, QPushButton, QMessageBox,
    QSizePolicy, QSpacerItem, QDialog, QDialogButtonBox, QLineEdit, QFormLayout,
    QDateEdit, QSpinBox, QStackedWidget, QGraphicsDropShadowEffect
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# ---------------------- Configuration ----------------------
BASE_URL = "http://localhost:8180"  # <-- change to your API server
API_PREFIX = "/api/v1"
APP_FONT = QFont("Segoe UI", 10)
SIDEBAR_EXPANDED_WIDTH = 220
SIDEBAR_COLLAPSED_WIDTH = 64

# ---------------------- Utilities ----------------------

def qurl(path: str) -> QUrl:
    if not path.startswith('/'):
        path = '/' + path
    return QUrl(BASE_URL.rstrip('/') + path)


def parse_reply_json(reply: QNetworkReply):
    raw = reply.readAll()
    try:
        text = bytes(raw).decode('utf-8')
        return json.loads(text)
    except Exception:
        return None


def human_name_from_climber(c: dict) -> str:
    parts = [c.get('first_name') or '', c.get('middle_name') or '', c.get('last_name') or '']
    return ' '.join([p for p in parts if p]).strip() or c.get('email') or 'Unknown'

# ---------------------- Small dialogs ----------------------

class SimpleFormDialog(QDialog):
    def __init__(self, title='Form', parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.layout = QVBoxLayout()
        self.form = QFormLayout()
        self.layout.addLayout(self.form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)

class GroupDialog(QDialog):
    def __init__(self, parent=None, group=None, nm: QNetworkAccessManager=None):
        super().__init__(parent)
        self.group = group or {}
        self.nm = nm
        self.setWindowTitle('Group')
        self.setup_ui()

    def setup_ui(self):
        v = QVBoxLayout()
        title = QLabel(self.group.get('group_name') or self.group.get('name') or 'Group')
        title.setStyleSheet('font-weight:700; font-size:16px;')
        v.addWidget(title)
        meta = QLabel(f"Leader: {self.group.get('leader_name','—')}  •  Start: {self.group.get('ascent_start_date','—')}")
        v.addWidget(meta)
        desc = QTextEdit(); desc.setReadOnly(True); desc.setPlainText(self.group.get('description',''))
        desc.setFixedHeight(140)
        v.addWidget(desc)
        btns = QHBoxLayout()
        members_btn = QPushButton('View members'); members_btn.clicked.connect(self.on_view_members)
        btns.addWidget(members_btn)
        v.addLayout(btns)
        close = QDialogButtonBox(QDialogButtonBox.Close); close.rejected.connect(self.reject)
        v.addWidget(close)
        self.setLayout(v)
        self.resize(480, 320)

    def on_view_members(self):
        gid = self.group.get('group_id') or self.group.get('id')
        if not gid:
            QMessageBox.information(self, 'Info', 'Group id not available')
            return
        if not self.nm:
            QMessageBox.warning(self, 'Error', 'Network manager not available')
            return
        req = QNetworkRequest(qurl(f"{API_PREFIX}/groups/{gid}/members"))
        reply = self.nm.get(req)
        reply.finished.connect(lambda r=reply: self._on_members_fetched(r))

    def _on_members_fetched(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, 'Error', f'Failed to fetch members: {reply.errorString()}')
            reply.deleteLater(); return
        data = parse_reply_json(reply)
        reply.deleteLater()
        members = data.get('members') if isinstance(data, dict) and 'members' in data else data
        dlg = QDialog(self); dlg.setWindowTitle('Members'); v = QVBoxLayout(); lw = QListWidget()
        if isinstance(members, list):
            for m in members:
                lw.addItem(human_name_from_climber(m))
        v.addWidget(lw); btns = QDialogButtonBox(QDialogButtonBox.Close); btns.rejected.connect(dlg.reject); v.addWidget(btns); dlg.setLayout(v); dlg.exec()

# ---------------------- Styled widgets ----------------------

class IconButton(QWidget):
    def __init__(self, icon_text: str, label: str):
        super().__init__()
        self.icon_label = QLabel(icon_text)
        self.icon_label.setFixedWidth(24)
        self.text_label = QLabel(label)
        self.text_label.setStyleSheet('color: #fff; font-weight:600;')
        lay = QHBoxLayout(); lay.setContentsMargins(8,6,8,6); lay.addWidget(self.icon_label); lay.addSpacing(8); lay.addWidget(self.text_label); lay.addStretch()
        self.setLayout(lay)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(48)

    def set_collapsed(self, collapsed: bool):
        self.text_label.setVisible(not collapsed)

# small card for group
class GroupCard(QFrame):
    def __init__(self, g: dict):
        super().__init__(); self.g = g
        self.setStyleSheet('background: #fff; border-radius:8px;')
        self.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=8, xOffset=0, yOffset=2))
        v = QVBoxLayout(); v.setContentsMargins(10,8,10,8)
        title = QLabel(g.get('group_name') or g.get('name') or 'Group')
        title.setStyleSheet('font-weight:700;')
        meta = QLabel(f"Leader: {g.get('leader_name','—')}  •  Start: {g.get('ascent_start_date','—')}")
        meta.setStyleSheet('color:#6b7280; font-size:12px;')
        desc = QLabel((g.get('description') or '')[:180])
        desc.setWordWrap(True)
        v.addWidget(title); v.addWidget(meta); v.addWidget(desc)
        self.setLayout(v)

# ---------------------- API wrapper ----------------------

class APIClient:
    def __init__(self, nm: QNetworkAccessManager):
        self.nm = nm

    def get(self, endpoint: str, cb):
        req = QNetworkRequest(qurl(f"{API_PREFIX}{endpoint}"))
        reply = self.nm.get(req)
        reply.finished.connect(lambda r=reply: cb(r))
        return reply

    def post(self, endpoint: str, payload: dict, cb):
        req = QNetworkRequest(qurl(f"{API_PREFIX}{endpoint}"))
        req.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')
        reply = self.nm.post(req, json.dumps(payload).encode('utf-8'))
        reply.finished.connect(lambda r=reply: cb(r))
        return reply

    def put(self, endpoint: str, payload: dict, cb):
        req = QNetworkRequest(qurl(f"{API_PREFIX}{endpoint}"))
        req.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')
        reply = self.nm.put(req, json.dumps(payload).encode('utf-8'))
        reply.finished.connect(lambda r=reply: cb(r))
        return reply

    def delete(self, endpoint: str, cb):
        req = QNetworkRequest(qurl(f"{API_PREFIX}{endpoint}"))
        reply = self.nm.deleteResource(req)
        reply.finished.connect(lambda r=reply: cb(r))
        return reply

# ---------------------- Mountains page (fixed) ----------------------

class MountainsPage(QWidget):
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api
        self.current_mountain = None
        self.setup_ui()

    def setup_ui(self):
        root = QHBoxLayout(); root.setSpacing(16)
        # LEFT: full mountain info
        left_card = QFrame(); left_card.setStyleSheet('background: rgba(255,255,255,0.95); border-radius:10px;')
        left_layout = QVBoxLayout(); left_layout.setContentsMargins(14,14,14,14)
        hdr = QLabel('<b>Mountain information</b>'); hdr.setStyleSheet('font-size:16px;')
        left_layout.addWidget(hdr)
        self.name_lbl = QLabel('Name: —'); self.name_lbl.setStyleSheet('font-weight:700; font-size:16px;')
        self.height_lbl = QLabel('Height: —'); self.country_lbl = QLabel('Country: —'); self.region_lbl = QLabel('Region: —')
        left_layout.addWidget(self.name_lbl); left_layout.addWidget(self.height_lbl); left_layout.addWidget(self.country_lbl); left_layout.addWidget(self.region_lbl)
        left_layout.addSpacing(6)
        left_layout.addWidget(QLabel('Description:'))
        self.desc = QTextEdit(); self.desc.setReadOnly(True); self.desc.setFixedHeight(160)
        left_layout.addWidget(self.desc)
        self.image = QLabel('Image placeholder'); self.image.setFixedSize(420, 240); self.image.setAlignment(Qt.AlignCenter)
        self.image.setStyleSheet('border:2px dashed #cbd5e1; border-radius:8px; color:#94a3b8;')
        left_layout.addWidget(self.image, alignment=Qt.AlignCenter)
        # action row
        action_row = QHBoxLayout()
        self.btn_add = QPushButton('Add mountain'); self.btn_add.clicked.connect(self.on_add)
        self.btn_edit = QPushButton('Edit mountain'); self.btn_edit.clicked.connect(self.on_edit)
        self.btn_refresh = QPushButton('Refresh'); self.btn_refresh.clicked.connect(self.on_refresh)
        action_row.addWidget(self.btn_add); action_row.addWidget(self.btn_edit); action_row.addWidget(self.btn_refresh)
        left_layout.addLayout(action_row)
        left_card.setLayout(left_layout)

        # RIGHT: groups list (chronological)
        right_card = QFrame(); right_card.setStyleSheet('background: rgba(255,255,255,0.95); border-radius:10px;')
        right_layout = QVBoxLayout(); right_layout.setContentsMargins(12,12,12,12)
        right_layout.addWidget(QLabel('<b>Groups (chronological)</b>'))
        self.groups_list = QListWidget(); self.groups_list.setSpacing(8)
        self.groups_list.itemClicked.connect(self.on_group_click)
        right_layout.addWidget(self.groups_list)
        right_card.setLayout(right_layout)

        root.addWidget(left_card, stretch=3)
        root.addWidget(right_card, stretch=2)
        self.setLayout(root)

    def load_mountain(self, mountain_id):
        if not mountain_id:
            return
        # fetch mountain detail
        self.api.get(f'/mountains/{mountain_id}', self._on_mountain_detail)
        # fetch groups
        self.api.get(f'/mountains/{mountain_id}/groups', self._on_groups)

    def _on_mountain_detail(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, 'Error', f'Failed to load mountain: {reply.errorString()}'); reply.deleteLater(); return
        data = parse_reply_json(reply); reply.deleteLater()
        if not isinstance(data, dict): return
        self.current_mountain = data
        self.name_lbl.setText(f"Name: {data.get('name','—')}")
        self.height_lbl.setText(f"Height: {data.get('height','—')}")
        self.country_lbl.setText(f"Country: {data.get('country','—')}")
        self.region_lbl.setText(f"Region: {data.get('region','—')}")
        self.desc.setPlainText(data.get('description',''))

    def _on_groups(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, 'Error', f'Failed to load groups: {reply.errorString()}'); reply.deleteLater(); return
        data = parse_reply_json(reply); reply.deleteLater()
        self.groups_list.clear()
        if not isinstance(data, list):
            return
        # ensure chronological: sort by ascent_start_date ascending
        try:
            data_sorted = sorted(data, key=lambda x: x.get('ascent_start_date') or '')
        except Exception:
            data_sorted = data
        for g in data_sorted:
            # build display text
            title = g.get('group_name') or g.get('name') or 'Group'
            leader = g.get('leader_name') or '—'
            start = g.get('ascent_start_date') or '—'
            status = g.get('ascent_status') or '—'
            members_count = g.get('members_count') or g.get('total_members_count') or '—'
            item = QListWidgetItem()
            widget = GroupCard({'group_name': title, 'leader_name': leader, 'ascent_start_date': start, 'description': g.get('description','')})
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.UserRole, g)
            self.groups_list.addItem(item)
            self.groups_list.setItemWidget(item, widget)

    def on_group_click(self, item: QListWidgetItem):
        g = item.data(Qt.UserRole)
        dlg = GroupDialog(self, group=g, nm=self.api.nm)
        dlg.exec()

    def on_add(self):
        dlg = SimpleFormDialog('Add mountain', self)
        name = QLineEdit(); height = QSpinBox(); height.setRange(0,100000)
        country = QLineEdit(); region = QLineEdit(); desc = QLineEdit()
        dlg.form.addRow('Name', name); dlg.form.addRow('Height', height); dlg.form.addRow('Country', country); dlg.form.addRow('Region', region); dlg.form.addRow('Description', desc)
        if dlg.exec() == QDialog.Accepted:
            payload = {'name': name.text(), 'height': height.value(), 'country': country.text(), 'region': region.text(), 'description': desc.text()}
            self.api.post('/mountains/', payload, self._on_added)

    def on_refresh(self):
        """
        Полная перезагрузка списка гор и отображение актуальной информации.
        Если страница находится внутри MainWindow — делегируем обновление комбо-списка
        туда (MainWindow.load_mountain_combo), чтобы не дублировать логику.
        В противном случае — сами запрашиваем /mountains/ и обновляем UI.
        """
        # Попробуем делегировать MainWindow (он уже знает, как правильно заполнить combo)
        wnd = self.window()
        if wnd is not None and hasattr(wnd, 'load_mountain_combo'):
            try:
                wnd.load_mountain_combo()
                return
            except Exception:
                # на случай, если вызов не удался — падать не будем, ниже будет fallback
                pass

                # Fallback: самостоятельно загрузим список гор и подгрузим подходящую (или первую) гору
        self.api.get('/mountains/', self._on_refresh_fetched)

    def _on_refresh_fetched(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, 'Error', f'Failed to refresh mountains: {reply.errorString()}')
            reply.deleteLater()
            return

        data = parse_reply_json(reply)
        reply.deleteLater()

        mountains = data if isinstance(data, list) else []
        # Если гор нет — очистим UI
        if not mountains:
            self.current_mountain = None
            self.name_lbl.setText('Name: —')
            self.height_lbl.setText('Height: —')
            self.country_lbl.setText('Country: —')
            self.region_lbl.setText('Region: —')
            self.desc.clear()
            self.groups_list.clear()
            return

        # Если текущая гора всё ещё присутствует в списке — просто её перезагрузим
        current_id = None
        if isinstance(self.current_mountain, dict):
            current_id = self.current_mountain.get('id')

        ids = [m.get('id') for m in mountains]
        if current_id and current_id in ids:
            # подгрузим детали для текущей выбранной горы
            self.load_mountain(current_id)
            return

        # Иначе — подгрузим первую гору из списка (fallback)
        first_mid = mountains[0].get('id')
        if first_mid:
            self.load_mountain(first_mid)


    def _on_added(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, 'Error', f'Create failed: {reply.errorString()}'); reply.deleteLater(); return
        QMessageBox.information(self, 'Success', 'Mountain created'); reply.deleteLater()
        self.on_refresh()  # автообновление после добавления

    def on_edit(self):
        if not self.current_mountain:
            QMessageBox.information(self, 'Info', 'No mountain selected')
            return
        mid = self.current_mountain.get('id')
        # check groups exist
        self.api.get(f'/mountains/{mid}/groups', lambda r: self._on_check_groups_before_edit(r))

    def _on_check_groups_before_edit(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, 'Error', f'Failed: {reply.errorString()}'); reply.deleteLater(); return
        data = parse_reply_json(reply); reply.deleteLater()
        if isinstance(data, list) and len(data) > 0:
            QMessageBox.information(self, 'Info', 'Cannot edit mountain: ascents exist for this mountain')
            return
        m = self.current_mountain
        dlg = SimpleFormDialog('Edit mountain', self)
        name = QLineEdit(m.get('name','')); height = QSpinBox(); height.setRange(0,100000); height.setValue(m.get('height') or 0)
        country = QLineEdit(m.get('country','')); region = QLineEdit(m.get('region','')); desc = QLineEdit(m.get('description',''))
        dlg.form.addRow('Name', name); dlg.form.addRow('Height', height); dlg.form.addRow('Country', country); dlg.form.addRow('Region', region); dlg.form.addRow('Description', desc)
        if dlg.exec() == QDialog.Accepted:
            payload = {'name': name.text(), 'height': height.value(), 'country': country.text(), 'region': region.text(), 'description': desc.text()}
            self.api.put(f"/mountains/{m.get('id')}", payload, self._on_updated)

    def _on_updated(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, 'Error', f'Update failed: {reply.errorString()}'); reply.deleteLater(); return
        QMessageBox.information(self, 'Success', 'Mountain updated'); reply.deleteLater()
        self.on_refresh()  # автообновление после обновления

# ---------------------- Minimal other pages (kept concise) ----------------------

class ClimbersPage(QWidget):
    def __init__(self, api: APIClient):
        super().__init__(); self.api = api; self.setup_ui()
    def setup_ui(self):
        v = QVBoxLayout(); h = QHBoxLayout(); h.addWidget(QLabel('<b>Climbers</b>'))
        self.btn_range = QPushButton('Filter by date range'); self.btn_range.clicked.connect(self.by_range); self.btn_refresh = QPushButton('Refresh'); self.btn_refresh.clicked.connect(self.refresh)
        h.addWidget(self.btn_range); h.addWidget(self.btn_refresh); v.addLayout(h)
        self.list = QListWidget(); v.addWidget(self.list); self.setLayout(v)
    def refresh(self):
        self.api.get('/climbers/', self._on_fetched)
    def _on_fetched(self, r: QNetworkReply):
        if r.error() != QNetworkReply.NetworkError.NoError: QMessageBox.warning(self,'Error',r.errorString()); r.deleteLater(); return
        data = parse_reply_json(r); r.deleteLater(); self.list.clear()
        if isinstance(data, list):
            for c in data: self.list.addItem(f"{human_name_from_climber(c)} — {c.get('email','')}")
    def by_range(self):
        dlg = QDialog(self); dlg.setWindowTitle('Climbers by date range'); lay = QVBoxLayout(); form = QFormLayout(); s = QDateEdit(); s.setCalendarPopup(True); s.setDate(QDate.currentDate().addMonths(-1)); e = QDateEdit(); e.setCalendarPopup(True); e.setDate(QDate.currentDate()); form.addRow('Start', s); form.addRow('End', e); lay.addLayout(form); btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject); lay.addWidget(btns); dlg.setLayout(lay)
        if dlg.exec() == QDialog.Accepted:
            ss = s.date().toString('yyyy-MM-dd'); ee = e.date().toString('yyyy-MM-dd'); self.api.get(f'/climbers/by-date-range?start={ss}&end={ee}', self._on_fetched)

class GroupsPage(QWidget):
    def __init__(self, api: APIClient): super().__init__(); self.api = api; self.setup_ui()
    def setup_ui(self): v = QVBoxLayout(); h = QHBoxLayout(); h.addWidget(QLabel('<b>Groups</b>')); btn_add = QPushButton('Add'); btn_add.clicked.connect(self.add); btn_refresh = QPushButton('Refresh'); btn_refresh.clicked.connect(self.refresh); h.addWidget(btn_add); h.addWidget(btn_refresh); v.addLayout(h); self.list = QListWidget(); v.addWidget(self.list); self.setLayout(v)
    def refresh(self): self.api.get('/groups/', self._on_fetched)
    def _on_fetched(self, r):
        if r.error() != QNetworkReply.NetworkError.NoError: QMessageBox.warning(self,'Error',r.errorString()); r.deleteLater(); return
        data = parse_reply_json(r); r.deleteLater(); self.list.clear();
        if isinstance(data, list):
            for g in data: self.list.addItem(f"{g.get('name')} — leader:{g.get('leader_id')}")
    def add(self):
        # minimal add (reuses earlier pattern)
        self.api.get('/mountains/', lambda r: self._prep_add(r))
    def _prep_add(self, r):
        if r.error() != QNetworkReply.NetworkError.NoError: QMessageBox.warning(self,'Error',r.errorString()); r.deleteLater(); return
        mountains = parse_reply_json(r) or []; r.deleteLater(); dlg = SimpleFormDialog('Add group', self)
        name = QLineEdit(); desc = QLineEdit(); leader = QSpinBox(); leader.setRange(0,100000); start = QDateEdit(); start.setCalendarPopup(True); start.setDate(QDate.currentDate())
        mc = QComboBox(); mc.addItem('Select', -1)
        for m in mountains: mc.addItem(f"{m.get('name')} ({m.get('country')})", m.get('id'))
        dlg.form.addRow('Name', name); dlg.form.addRow('Mountain', mc); dlg.form.addRow('Leader id', leader); dlg.form.addRow('Start', start); dlg.form.addRow('Description', desc)
        if dlg.exec() == QDialog.Accepted:
            mid = mc.currentData();
            if mid == -1: QMessageBox.information(self,'Info','Select mountain'); return
            payload = {'name': name.text(), 'description': desc.text(), 'leader_id': leader.value(), 'mountain_id': mid, 'start_date': start.date().toString('yyyy-MM-dd')}
            self.api.post('/groups/', payload, lambda rr: (QMessageBox.information(self,'Success','Group created') if rr.error()==QNetworkReply.NetworkError.NoError else QMessageBox.warning(self,'Error',rr.errorString()), rr.deleteLater(), self.refresh()))

class AscentsPage(QWidget):
    def __init__(self, api: APIClient): super().__init__(); self.api = api; self.setup_ui()
    def setup_ui(self): v = QVBoxLayout(); h = QHBoxLayout(); h.addWidget(QLabel('<b>Ascents</b>')); btn_range = QPushButton('By range'); btn_range.clicked.connect(self.filter); btn_up = QPushButton('Upcoming'); btn_up.clicked.connect(self.upcoming); h.addWidget(btn_range); h.addWidget(btn_up); v.addLayout(h); self.list = QListWidget(); v.addWidget(self.list); self.setLayout(v)
    def filter(self):
        dlg = QDialog(self);
        dlg.setWindowTitle('Ascents by date range'); lay = QVBoxLayout(); form = QFormLayout(); s = QDateEdit(); s.setCalendarPopup(True); s.setDate(QDate.currentDate().addMonths(-1)); e = QDateEdit(); e.setCalendarPopup(True); e.setDate(QDate.currentDate()); form.addRow('Start', s); form.addRow('End', e); lay.addLayout(form); btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject); lay.addWidget(btns);
        dlg.setLayout(lay)
        if dlg.exec() == QDialog.Accepted:
            ss = s.date().toString('yyyy-MM-dd'); ee = e.date().toString('yyyy-MM-dd'); self.api.get(f'/ascents/by-date-range?start={ss}&end={ee}', self._on_fetched)
    def upcoming(self): self.api.get('/ascents/upcoming', self._on_fetched)
    def _on_fetched(self, r):
        if r.error() != QNetworkReply.NetworkError.NoError: QMessageBox.warning(self,'Error',r.errorString()); r.deleteLater(); return
        data = parse_reply_json(r); r.deleteLater(); self.list.clear()
        if isinstance(data, list):
            for a in data:
                mountain = a.get('mountain_name') or (a.get('mountain') or {}).get('name') or '—'
                group = a.get('group_name') or (a.get('group') or {}).get('name') or '—'
                self.list.addItem(f"{mountain} — {group} — {a.get('start_date')} -> {a.get('end_date')} — {a.get('status')}")

class StatsPage(QWidget):
    def __init__(self, api: APIClient): super().__init__(); self.api = api; self.setup_ui()
    def setup_ui(self): v = QVBoxLayout(); h = QHBoxLayout(); h.addWidget(QLabel('<b>Stats</b>')); btn = QPushButton('Refresh'); btn.clicked.connect(self.refresh); h.addWidget(btn); v.addLayout(h); self.text = QTextEdit(); self.text.setReadOnly(True); v.addWidget(self.text); self.setLayout(v)
    def refresh(self): self.api.get('/mountains/stats', self._on_fetched)
    def _on_fetched(self, r):
        if r.error() != QNetworkReply.NetworkError.NoError: QMessageBox.warning(self,'Error',r.errorString()); r.deleteLater(); return
        data = parse_reply_json(r); r.deleteLater();
        if not isinstance(data, list): self.text.setPlainText('No stats'); return
        lines = []
        for m in data:
            lines.append(f"{m.get('name')} ({m.get('height')}) — ascents: {m.get('ascents_count')} — unique groups/visitors: {m.get('unique_groups_count')}")
        self.text.setPlainText('\n'.join(lines))

# ---------------------- Main Window with animated sidebar ----------------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Alpine Club — Mountains & Ascents')
        self.setMinimumSize(1200, 760)
        self.setFont(APP_FONT)
        self.nm = QNetworkAccessManager(self)
        self.api = APIClient(self.nm)
        self.sidebar_expanded = True
        self.setup_ui()

    def setup_ui(self):
        root = QHBoxLayout(); root.setSpacing(0)
        # Sidebar
        self.sidebar = QFrame(); self.sidebar.setObjectName('sidebar'); self.sidebar.setStyleSheet('background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0f172a, stop:1 #071122);')
        self.sidebar.setMaximumWidth(SIDEBAR_EXPANDED_WIDTH)
        s_layout = QVBoxLayout(); s_layout.setContentsMargins(10,12,10,12)
        # collapse toggle
        self.toggle_btn = QPushButton('⟨')
        self.toggle_btn.setFixedSize(36,36)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        s_layout.addWidget(self.toggle_btn, alignment=Qt.AlignRight)
        # logo
        logo = QLabel('⛰️  Alpine Club'); logo.setStyleSheet('color:#fff; font-weight:800; font-size:16px;')
        s_layout.addWidget(logo)
        s_layout.addSpacing(6)
        # nav buttons (IconButton widgets)
        self.nav_buttons = {}
        nav_items = [('mountains','⛰️','Mountains'), ('climbers','🧗','Climbers'), ('groups','👥','Groups'), ('ascents','📅','Ascents'), ('stats','📊','Stats')]
        for key, ico, label in nav_items:
            btn = IconButton(ico, label)
            btn.mousePressEvent = lambda ev, k=key: self.switch(k)
            s_layout.addWidget(btn)
            self.nav_buttons[key] = btn
        s_layout.addStretch()
        self.sidebar.setLayout(s_layout)

        # Main area
        main = QVBoxLayout(); main.setContentsMargins(12,12,12,12)
        # Header
        header = QHBoxLayout()
        self.title_label = QLabel('—'); self.title_label.setStyleSheet('font-size:20px; font-weight:800;')
        self.title_label.setAlignment(Qt.AlignCenter)
        self.mountain_combo = QComboBox(); self.mountain_combo.setMinimumWidth(340); self.mountain_combo.currentIndexChanged.connect(self.on_combo_change)
        header.addStretch(); header.addWidget(self.title_label); header.addSpacing(12); header.addWidget(self.mountain_combo); header.addStretch()
        main.addLayout(header)
        # Stacked content
        self.stack = QStackedWidget()
        self.page_mountains = MountainsPage(self.api)
        self.page_climbers = ClimbersPage(self.api)
        self.page_groups = GroupsPage(self.api)
        self.page_ascents = AscentsPage(self.api)
        self.page_stats = StatsPage(self.api)
        self.stack.addWidget(self.page_mountains); self.stack.addWidget(self.page_climbers); self.stack.addWidget(self.page_groups); self.stack.addWidget(self.page_ascents); self.stack.addWidget(self.page_stats)
        main.addWidget(self.stack)

        # assemble
        root.addWidget(self.sidebar)
        content_frame = QFrame(); content_frame.setLayout(main)
        root.addWidget(content_frame, stretch=1)
        self.setLayout(root)

        # default
        self.switch('mountains')
        self.load_mountain_combo()

    def toggle_sidebar(self):
        start = SIDEBAR_EXPANDED_WIDTH if self.sidebar_expanded else SIDEBAR_COLLAPSED_WIDTH
        end = SIDEBAR_COLLAPSED_WIDTH if self.sidebar_expanded else SIDEBAR_EXPANDED_WIDTH
        anim = QPropertyAnimation(self.sidebar, b"maximumWidth")
        anim.setDuration(280)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.start()
        # hide/show labels on buttons
        for btn in self.nav_buttons.values():
            btn.set_collapsed(self.sidebar_expanded)
        # change toggle sign
        self.toggle_btn.setText('⟩' if self.sidebar_expanded else '⟨')
        self.sidebar_expanded = not self.sidebar_expanded
        # keep reference to animation so it doesn't get GC'd
        self._sidebar_anim = anim

    def switch(self, key: str):
        mapping = {'mountains':0, 'climbers':1, 'groups':2, 'ascents':3, 'stats':4}
        idx = mapping.get(key, 0)
        self.stack.setCurrentIndex(idx)
        page = self.stack.currentWidget()
        if hasattr(page, 'refresh'):
            try: page.refresh()
            except Exception: pass
        # style active nav
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.setStyleSheet('background: rgba(255,255,255,0.05);')
            else:
                btn.setStyleSheet('background: transparent;')

    def load_mountain_combo(self):
        self.api.get('/mountains/', self._on_combo_loaded)

    def _on_combo_loaded(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            reply.deleteLater(); return
        data = parse_reply_json(reply); reply.deleteLater(); items = data if isinstance(data, list) else []
        self.mountain_combo.blockSignals(True); self.mountain_combo.clear(); self.mountain_combo.addItem('Select mountain', -1)
        for m in items: self.mountain_combo.addItem(f"{m.get('name')} ({m.get('country')})", m.get('id'))
        self.mountain_combo.blockSignals(False)
        if items:
            # select first
            self.mountain_combo.setCurrentIndex(1)
            self.title_label.setText(items[0].get('name') or '—')
            mid = items[0].get('id')
            if mid:
                self.page_mountains.load_mountain(mid)

    def on_combo_change(self, idx: int):
        mid = self.mountain_combo.currentData()
        if mid is None or mid == -1: return
        name = self.mountain_combo.currentText().split('(')[0].strip()
        self.title_label.setText(name)
        # ensure mountains page displays selected mountain
        self.page_mountains.load_mountain(mid)

# ---------------------- App entry ----------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
