# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnKill
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestKillsQuest(ClassTypeQuest):
    kills_count = IntField(caption=u"Сумма для накопления")

    def init_text(self):
        pass

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.kills = 0
        self.log(text=self.locale("q_cq_kills_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCPageNote,
                time=event.time,
                page_caption=quest.locale("q_cq_kills_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_kills_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.dc.kills >= quest.kills_count:
                    quest.agent.profile.quest_note(uid=quest.dc.visited_note, time=event.time)
                    quest.go(event=event, new_state="win")
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("q_cq_kills_replica_not_finish"),  ##LOCALIZATION
                        event=event
                    )

            if isinstance(event, OnKill) and event.agent and quest.agent.profile.get_real_lvl() <= event.agent.profile.get_real_lvl():
                quest.dc.kills += 1  # info: здесь будут засчитываться одни и те же цели.
                quest.log(text=u'{} {}.'.format(event.agent.profile._agent_model.print_login(),
                                                quest.locale("q_cq_kills_target_killed")), event=event,  ##LOCALIZATION
                          position=quest.hirer.hometown.position)  # заменить на позицию машинки убийцы


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_kills_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
