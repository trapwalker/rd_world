# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnKill
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, LocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestKillsQuest(ClassTypeQuest):
    kills_count = IntField(caption=u"Сумма для накопления")

    def init_text(self):
        self.text = LocalizedString(
            en=u"{}, {}<br>{}".format(
                self.agent.login,
                self.locale(key="q_cq_kills_task_text", loc="en"),
                self.locale(key="q_cq_journal_reward_1", loc="en"),
            ),
            ru=u"{}, {}<br>{}".format(
                self.agent.login,
                self.locale(key="q_cq_kills_task_text", loc="ru"),
                self.locale(key="q_cq_journal_reward_1", loc="ru"),
            ),
        )

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.kills = 0
        self.log(text=self.locale("q_cq_kills_started"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.KillsClassQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_kills_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_kills_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.dc.kills >= quest.kills_count:
                    quest.go(event=event, new_state="back_to_teacher")
                else:
                    text = LocalizedString(_id="q_cq_kills_replica_not_finish").generate(  ##LOCALIZATION
                        complete=quest.dc.kills,
                        count=quest.kills_count
                    )
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=text,
                        event=event
                    )

            if isinstance(event, OnKill) and event.agent \
                    and quest.agent.profile.get_real_lvl() <= event.agent.profile.get_real_lvl():

                quest.dc.kills += 1  # info: здесь будут засчитываться одни и те же цели.
                quest.log(quest.locale("q_cq_kills_target_killed").format(event.agent.profile._agent_model.print_login()),
                          event=event)  ##LOCALIZATION

                if quest.dc.kills >= quest.kills_count:
                    quest.log(text=quest.locale("q_cq_kills_back_to_teacher"), event=event)  ##LOCALIZATION
                    quest.go(event=event, new_state="back_to_teacher")
    ####################################################################################################################
    class back_to_teacher(QuestState_):
        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                quest.agent.profile.set_exp(time=event.time, dvalue=3000)
                quest.go(event=event, new_state="win")
    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.npc_replica(
                npc=quest.hirer,
                replica=quest.locale("q_cq_kills_task_phrase_success"),  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_kills_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
