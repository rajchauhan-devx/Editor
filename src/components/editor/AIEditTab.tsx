import React,{useEffect,useState} from 'react';
import {Project} from '../../types';
import {fetchProjectData} from '../../services/workerApi';
import {Panel} from '../Panel';
export function AIEditTab({project}:{project?:Project}){const [plan,setPlan]=useState<any>(null);useEffect(()=>{let alive=true;if(project)fetchProjectData(project.id).then(d=>{if(alive)setPlan(d?.edit_plan);});return()=>{alive=false;};},[project?.id]);return <Panel title="AI edit plan">{plan?<><p>{plan.story_summary}</p><pre className="text-xs whitespace-pre-wrap bg-slate-950 p-4 rounded">{JSON.stringify(plan,null,2)}</pre></>:<p>No edit plan yet. Start analysis from the project progress screen.</p>}<p>AI self-review, effect controls and manual timeline editing are not yet implemented.</p></Panel>;}
