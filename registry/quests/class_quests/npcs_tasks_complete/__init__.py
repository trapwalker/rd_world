# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnQuestChange, OnNote
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import ListField, RegistryLinkField, LocalizedString, IntField

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestNPCsTasksComplete(ClassTypeQuest):
    tasks_count = IntField(caption="Количество заданий у каждого НПЦ")
    npcs = ListField(
        caption=u"НПЦ, у которых нужно выполнить задания",
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.poi.Institution'),
    )

    def init_text(self):
        pass

    def check_tasks(self):
        for npc in self.npcs:
            npc_uri = npc.uri
            if self.dc.tasks.get(npc_uri, 0) < self.tasks_count:
                return False
        return True

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.tasks = dict()
        self.log(text=self.locale("q_cq_npc_tasks_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCPageNote,
                time=event.time,
                page_caption=quest.locale("q_cq_npc_tasks_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_npc_tasks_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.check_tasks():
                    quest.go(event=event, new_state="win")  # Все города посещены!
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("q_cq_npc_tasks_replica_not_finish"),  ##LOCALIZATION
                        event=event
                    )

            if isinstance(event, OnQuestChange):
                target_quest = quest.agent.profile.get_quest(event.target_quest_uid)
                if target_quest and target_quest.result == 'win':  # info: так определяем завершённые квесты
                    if target_quest.hirer and target_quest.hirer in quest.npcs:
                        text = LocalizedString(_id='q_cq_npc_tasks_add_one').generate(
                            npc_title=quest.locale(quest.locale(target_quest.hirer.title)))  ##LOCALIZATION
                        quest.log(text=text, event=event)
                        if quest.dc.tasks.get(target_quest.hirer.uri, None):
                            quest.dc.tasks[target_quest.hirer.uri] += 1
                        else:
                            quest.dc.tasks[target_quest.hirer.uri] = 1
                        if quest.check_tasks():
                            quest.log(text=quest.locale("q_cq_npc_tasks_back_to_teacher"),
                                      event=event)  ##LOCALIZATION
                            quest.go(event=event, new_state="back_to_teacher")


    class back_to_teacher(QuestState_):
        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                quest.go(event=event, new_state="win")


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_npc_tasks_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
