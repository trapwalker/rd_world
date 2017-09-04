# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)


from sublayers_world.registry.quests.agent_event_quests import AgentEventQuest
from sublayers_server.model.registry_me.classes.notes import NPCWantedBossNote, MapMarkerNote
from sublayers_server.model.quest_events import OnKill, OnNote, OnTimer, OnQuestSee, OnQuestOut
from sublayers_server.model.registry_me.classes.quests import QuestState_, FailByCancelState, WinState
from sublayers_server.model.registry_me.tree import LocalizedString

from functools import partial


class KillBossQuest(AgentEventQuest):

    def as_client_dict(self):
        d = super(KillBossQuest, self).as_client_dict()
        d.update(
            is_kill=self.dc.is_kill,
            boss_name=self.dc.boss_name,
            boss_avatar=self.dc.boss_avatar,
            boss_reward=self.reward_money
        )
        return d

    def get_event_quest(self, event):
        event_quest = super(KillBossQuest, self).get_event_quest(event=event)
        self.dc.is_kill = False
        if event_quest:
            self.dc.boss_name = event_quest.dc._main_agent.print_login()
            self.dc.boss_avatar = event_quest.dc._main_agent.avatar_link
        else:
            self.dc.boss_name = u''
            self.dc.boss_avatar = u''
        return event_quest

    def can_cancel(self, event):
        money_penalty = round(self.reward_money / 2)
        agent = self.agent.profile
        if agent.balance >= money_penalty:
            agent.set_balance(time=event.time, delta=-money_penalty)
            self.log(text=u'{} {}nc.'.format(self.locale("q_kb_cancel_done"), money_penalty), event=event)  #LOCALIZATION
            return True
        else:
            self.npc_replica(npc=self.hirer, replica=u"{} {}nc.".format(self.locale("q_kb_cancel_try"), money_penalty), event=event)  #LOCALIZATION
            return False

    def init_level(self):
        self.level = 1

    def init_text(self, event):
        self.text_short = LocalizedString(
            en=u"Убейте игрока.",  # TODO: ##LOCALIZATION
            ru=u"Убейте игрока.",
        )
        event_quest = self.get_event_quest(event=event)
        if event_quest:
            self.text = LocalizedString(
                en=u"Убейте игрока с ником {}. Награда: {:.0f}nc.".format(  # TODO: ##LOCALIZATION
                    event_quest.dc._main_agent.print_login(),
                    event_quest.dc.kill_reward_money,
                ),
                ru=u"Убейте игрока с ником {}. Награда: {:.0f}nc.".format(
                    event_quest.dc._main_agent.print_login(),
                    event_quest.dc.kill_reward_money,
                ),
            )

    def on_generate_(self, event, **kw):
        super(KillBossQuest, self).on_generate_(event=event, **kw)
        self.init_level()
        self.init_text(event=event)

    def on_start_(self, event, **kw):
        # Создание ноты для квеста
        self.dc.track_note_uid = None
        self.dc.see_target = False
        self.dc.wanted_note_uid = self.agent.profile.add_note(
            quest_uid=self.uid,
            note_class=NPCWantedBossNote,
            time=event.time,
            npc=self.hirer,
            page_caption=self.locale("q_kb_note_caption"),  #LOCALIZATION
        )
        self.log(text=self.locale("q_kb_quest_is_started"), event=event)  #LOCALIZATION

    ####################################################################################################################
    class begin(AgentEventQuest.begin):
        def on_enter_(self, quest, event):
            super(KillBossQuest.begin, self).on_enter_(quest=quest, event=event)
            quest.set_timer(event=event, name='last_track', delay=10)

        def on_event_(self, quest, event):
            super(KillBossQuest.begin, self).on_event_(quest=quest, event=event)
            go = partial(quest.go, event=event)

            event_quest = quest.get_event_quest(event=event)
            if not event_quest:
                return

            if isinstance(event, OnKill) and (event.agent is event_quest.dc._main_agent.example):
                quest.dc.is_kill = True
                quest.log(text=u'{} {}'.format(quest.dc.boss_name, quest.locale("q_kb_killed")), event=event)  #LOCALIZATION
                go('note_kill_reward')

            if isinstance(event, OnQuestSee) and (event.obj is event_quest.dc._main_agent.car):
                quest.agent.profile.del_note(uid=quest.dc.track_note_uid, time=event.time)
                quest.dc.see_target = True

            if isinstance(event, OnQuestOut) and (event.obj is event_quest.dc._main_agent.car):
                quest.dc.see_target = False

            if isinstance(event, OnTimer) and (event.name == 'last_track'):
                quest.agent.profile.del_note(uid=quest.dc.track_note_uid, time=event.time)
                if not quest.dc.see_target and event_quest.dc._main_agent.car:
                    quest.dc.track_note_uid = quest.agent.profile.add_note(
                        quest_uid=quest.uid,
                        note_class=MapMarkerNote,
                        time=event.time,
                        position=event_quest.dc._main_agent.car.position(time=event.time),
                        radius=10,
                    )
                quest.set_timer(event=event, name='last_track', delay=10)

    ####################################################################################################################
    class note_kill_reward(QuestState_):
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnNote) and (quest.dc.wanted_note_uid == event.note_uid) and (event.result == True):
                go('reward')

    ####################################################################################################################
    class reward(WinState):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            quest.agent.profile.set_balance(time=event.time, delta=quest.reward_money)
            quest.agent.profile.set_karma(time=event.time, dvalue=quest.reward_karma)
            go('win')

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.agent.profile.del_note(uid=quest.dc.wanted_note_uid, time=event.time)
            quest.agent.profile.del_note(uid=quest.dc.track_note_uid, time=event.time)

    ####################################################################################################################
    class fail(FailByCancelState):
        def on_enter_(self, quest, event):
            if not quest.dc.is_kill:
                quest.log(text=quest.locale("q_kb_killed_by_another"), event=event)  #LOCALIZATION
            quest.agent.profile.del_note(uid=quest.dc.wanted_note_uid, time=event.time)
            quest.agent.profile.del_note(uid=quest.dc.track_note_uid, time=event.time)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            if not quest.dc.is_kill:
                quest.log(text=quest.locale("q_kb_killed_by_another"), event=event)  #LOCALIZATION
            quest.agent.profile.del_note(uid=quest.dc.wanted_note_uid, time=event.time)
            quest.agent.profile.del_note(uid=quest.dc.track_note_uid, time=event.time)

