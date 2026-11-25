import React, { useState, useEffect, useMemo } from 'react';
import {
  Check,
  Plus,
  Search,
  Trash2,
  Edit,
  Calendar,
  LayoutKanban,
  List as ListIcon,
  BarChart3,
  Sun,
  Moon,
  Menu,
  X,
  Inbox,
  Sparkles,
  CheckCircle2,
  Clock,
  Download
} from 'lucide-react';
import confetti from 'canvas-confetti';

export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'todo' | 'in_progress' | 'review' | 'completed';
  priority: 'urgent' | 'high' | 'medium' | 'low';
  project: string;
  dueDate: string;
  tags: string[];
  createdAt: string;
}

const INITIAL_TASKS: Task[] = [
  {
    id: 'task-1',
    title: 'Deploy Q4 Infrastructure on AWS ECS Cluster',
    description: 'Configure autoscaling policies, target groups, and CloudWatch alert triggers for high-traffic peak.',
    status: 'in_progress',
    priority: 'urgent',
    project: 'Engineering',
    dueDate: '2026-11-25',
    tags: ['Cloud', 'DevOps'],
    createdAt: '2026-11-20'
  },
  {
    id: 'task-2',
    title: 'Finalize Design System Tokens & Dark Theme in Figma',
    description: 'Align color scales, typography ramps, and button states for the new v3 design overhaul.',
    status: 'completed',
    priority: 'high',
    project: 'Design',
    dueDate: '2026-11-22',
    tags: ['Figma', 'UI/UX'],
    createdAt: '2026-11-18'
  },
  {
    id: 'task-3',
    title: 'Implement Stripe Billing Webhook & Subscription Tiers',
    description: 'Add idempotency handling, invoice generation webhook listeners, and upgraded plan triggers.',
    status: 'in_progress',
    priority: 'urgent',
    project: 'Engineering',
    dueDate: '2026-11-26',
    tags: ['Payments', 'Backend'],
    createdAt: '2026-11-21'
  },
  {
    id: 'task-4',
    title: 'Launch Black Friday SaaS Growth Email Campaign',
    description: 'Set up behavioral drip sequence in Customer.io with A/B subject line testing.',
    status: 'todo',
    priority: 'medium',
    project: 'Marketing',
    dueDate: '2026-11-28',
    tags: ['Growth', 'Email'],
    createdAt: '2026-11-22'
  },
  {
    id: 'task-5',
    title: 'Security Audit & OAuth2 Token Refresh Verification',
    description: 'Review JWT expiry rotation, CSRF guards, and conduct automated static dependency scanning.',
    status: 'review',
    priority: 'high',
    project: 'Security',
    dueDate: '2026-11-24',
    tags: ['Auth', 'Security'],
    createdAt: '2026-11-19'
  }
];

const PROJECTS = [
  { name: 'All Projects', color: 'bg-slate-500' },
  { name: 'Engineering', color: 'bg-indigo-500' },
  { name: 'Design', color: 'bg-pink-500' },
  { name: 'Marketing', color: 'bg-amber-500' },
  { name: 'Security', color: 'bg-red-500' },
  { name: 'Executive', color: 'bg-emerald-500' }
];

const STATUS_COLUMNS = [
  { id: 'todo', title: 'Backlog / To Do', badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300' },
  { id: 'in_progress', title: 'In Progress', badge: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300' },
  { id: 'review', title: 'In Review', badge: 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300' },
  { id: 'completed', title: 'Completed', badge: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300' }
];

const PRIORITIES = {
  urgent: { label: 'Urgent', color: 'text-red-600 bg-red-50 border-red-200 dark:bg-red-950/40 dark:text-red-400 dark:border-red-900/60' },
  high: { label: 'High', color: 'text-amber-600 bg-amber-50 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-900/60' },
  medium: { label: 'Medium', color: 'text-blue-600 bg-blue-50 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900/60' },
  low: { label: 'Low', color: 'text-slate-600 bg-slate-50 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700' }
};

export default function App() {
  const [tasks, setTasks] = useState<Task[]>(() => {
    try {
      const cached = localStorage.getItem('pulsetask_tasks_v2');
      return cached ? JSON.parse(cached) : INITIAL_TASKS;
    } catch {
      return INITIAL_TASKS;
    }
  });

  const [isDarkMode, setIsDarkMode] = useState(() => {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  const [activeView, setActiveView] = useState<'list' | 'kanban' | 'analytics'>('list');
  const [selectedNav, setSelectedNav] = useState('all');
  const [selectedProject, setSelectedProject] = useState('All Projects');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'dueDate' | 'priority' | 'title' | 'createdAt'>('dueDate');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Partial<Task> | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem('pulsetask_tasks_v2', JSON.stringify(tasks));
    } catch (e) {
      console.error(e);
    }
  }, [tasks]);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleToggleComplete = (id: string) => {
    setTasks(prev => prev.map(t => {
      if (t.id === id) {
        const nextStatus = t.status === 'completed' ? 'todo' : 'completed';
        if (nextStatus === 'completed') {
          confetti({ particleCount: 50, spread: 60, origin: { y: 0.8 } });
        }
        return { ...t, status: nextStatus };
      }
      return t;
    }));
  };

  const handleSaveTask = (taskData: Omit<Task, 'id' | 'createdAt' | 'tags'> & { tags?: string[] }) => {
    if (editingTask && 'id' in editingTask && editingTask.id) {
      setTasks(prev => prev.map(t => t.id === editingTask.id ? { ...t, ...taskData } : t));
      showToast('Task updated successfully');
    } else {
      const newTask: Task = {
        id: 'task-' + Date.now(),
        ...taskData,
        tags: taskData.tags || [],
        createdAt: new Date().toISOString().split('T')[0]
      };
      setTasks(prev => [newTask, ...prev]);
      showToast('New task created');
    }
    setIsModalOpen(false);
    setEditingTask(null);
  };

  const handleDeleteTask = (id: string) => {
    const deleted = tasks.find(t => t.id === id);
    setTasks(prev => prev.filter(t => t.id !== id));
    showToast(`Deleted "${deleted?.title?.slice(0, 20)}..."`);
  };

  const handleStatusChange = (id: string, newStatus: Task['status']) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, status: newStatus } : t));
  };

  const filteredTasks = useMemo(() => {
    const todayStr = new Date().toISOString().split('T')[0];

    return tasks.filter(task => {
      if (selectedNav === 'today' && task.dueDate !== todayStr) return false;
      if (selectedNav === 'upcoming' && (!task.dueDate || task.dueDate <= todayStr)) return false;
      if (selectedNav === 'completed' && task.status !== 'completed') return false;
      if (selectedProject !== 'All Projects' && task.project !== selectedProject) return false;
      if (priorityFilter !== 'all' && task.priority !== priorityFilter) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return task.title.toLowerCase().includes(q) || task.description.toLowerCase().includes(q);
      }
      return true;
    }).sort((a, b) => {
      if (sortBy === 'dueDate') {
        if (!a.dueDate) return 1;
        if (!b.dueDate) return -1;
        return a.dueDate.localeCompare(b.dueDate);
      }
      if (sortBy === 'priority') {
        const weights = { urgent: 4, high: 3, medium: 2, low: 1 };
        return (weights[b.priority] || 0) - (weights[a.priority] || 0);
      }
      if (sortBy === 'title') {
        return a.title.localeCompare(b.title);
      }
      return b.createdAt.localeCompare(a.createdAt);
    });
  }, [tasks, selectedNav, selectedProject, priorityFilter, searchQuery, sortBy]);

  const stats = useMemo(() => {
    const total = tasks.length;
    const completed = tasks.filter(t => t.status === 'completed').length;
    const inProgress = tasks.filter(t => t.status === 'in_progress').length;
    const todayStr = new Date().toISOString().split('T')[0];
    const overdue = tasks.filter(t => t.status !== 'completed' && t.dueDate && t.dueDate < todayStr).length;
    const rate = total === 0 ? 0 : Math.round((completed / total) * 100);

    return { total, completed, inProgress, overdue, rate };
  }, [tasks]);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-[#0b0f19]">
      {/* Sidebar */}
      <aside className={`${isSidebarOpen ? 'w-64' : 'w-20'} flex-shrink-0 bg-white dark:bg-[#111827] border-r border-slate-200 dark:border-slate-800 flex flex-col justify-between transition-all duration-300 z-30`}>
        <div>
          <div className="h-16 flex items-center justify-between px-5 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center space-x-3 overflow-hidden">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 flex-shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              {isSidebarOpen && (
                <div className="flex flex-col">
                  <span className="font-extrabold text-base tracking-tight bg-gradient-to-r from-slate-900 to-slate-700 dark:from-white dark:to-slate-300 bg-clip-text text-transparent">PulseTask</span>
                  <span className="text-[10px] text-indigo-600 dark:text-indigo-400 font-semibold uppercase tracking-wider">Enterprise SaaS</span>
                </div>
              )}
            </div>
            <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800">
              <Menu className="w-4 h-4" />
            </button>
          </div>

          <div className="px-3 py-3 space-y-1">
            {[
              { id: 'all', label: 'All Tasks', icon: Inbox, count: stats.total },
              { id: 'today', label: 'Due Today', icon: Calendar, count: tasks.filter(t => t.dueDate === new Date().toISOString().split('T')[0]).length },
              { id: 'upcoming', label: 'Upcoming', icon: Clock, count: tasks.filter(t => t.dueDate && t.dueDate > new Date().toISOString().split('T')[0]).length },
              { id: 'completed', label: 'Completed', icon: CheckCircle2, count: stats.completed },
            ].map(item => {
              const ItemIcon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => { setSelectedNav(item.id); setSelectedProject('All Projects'); }}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                    selectedNav === item.id 
                      ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 font-semibold shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <ItemIcon className="w-4 h-4" />
                    {isSidebarOpen && <span>{item.label}</span>}
                  </div>
                  {isSidebarOpen && (
                    <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-slate-100 dark:bg-slate-800 text-slate-500">
                      {item.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {isSidebarOpen && (
            <div className="px-3 pt-4">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-3 mb-2">Projects</div>
              <div className="space-y-0.5">
                {PROJECTS.map(proj => (
                  <button
                    key={proj.name}
                    onClick={() => setSelectedProject(proj.name)}
                    className={`w-full flex items-center space-x-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      selectedProject === proj.name
                        ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/40'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${proj.color}`}></span>
                    <span className="truncate">{proj.name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="p-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className="p-2 rounded-xl text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs flex items-center space-x-2 ml-auto"
          >
            {isDarkMode ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-slate-600" />}
            {isSidebarOpen && <span className="text-xs">{isDarkMode ? 'Light' : 'Dark'}</span>}
          </button>
        </div>
      </aside>

      {/* Main Container */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white dark:bg-[#111827] border-b border-slate-200 dark:border-slate-800 px-6 flex items-center justify-between flex-shrink-0 z-20">
          <div className="flex items-center flex-1 max-w-md relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tasks, descriptions... (Press /)"
              className="w-full bg-slate-100 dark:bg-slate-800/80 text-sm text-slate-900 dark:text-slate-100 pl-10 pr-4 py-2 rounded-xl border border-transparent focus:border-indigo-500 focus:bg-white dark:focus:bg-[#0b0f19] outline-none transition-all placeholder:text-slate-400"
            />
          </div>

          <div className="flex items-center space-x-3 ml-4">
            <div className="bg-slate-100 dark:bg-slate-800 p-1 rounded-xl flex items-center space-x-1 border border-slate-200/60 dark:border-slate-700/60">
              <button
                onClick={() => setActiveView('list')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeView === 'list'
                    ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                <ListIcon className="w-3.5 h-3.5" />
                <span>List</span>
              </button>
              <button
                onClick={() => setActiveView('kanban')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeView === 'kanban'
                    ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                <LayoutKanban className="w-3.5 h-3.5" />
                <span>Board</span>
              </button>
              <button
                onClick={() => setActiveView('analytics')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeView === 'analytics'
                    ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" />
                <span>Analytics</span>
              </button>
            </div>

            <button
              onClick={() => { setEditingTask(null); setIsModalOpen(true); }}
              className="flex items-center space-x-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-semibold text-sm px-4 py-2 rounded-xl shadow-md shadow-indigo-500/25 transition-all transform active:scale-95"
            >
              <Plus className="w-4 h-4" />
              <span>New Task</span>
            </button>
          </div>
        </header>

        {/* Task List / View */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto space-y-3">
            {filteredTasks.map(task => {
              const isDone = task.status === 'completed';
              return (
                <div
                  key={task.id}
                  className={`group bg-white dark:bg-[#111827] border rounded-2xl p-4 shadow-sm hover:shadow-md transition-all flex items-center justify-between gap-4 ${
                    isDone 
                      ? 'border-slate-200/60 dark:border-slate-800/60 opacity-60 bg-slate-50/50 dark:bg-slate-900/30'
                      : 'border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-700'
                  }`}
                >
                  <div className="flex items-center space-x-3.5 flex-1 min-w-0">
                    <button
                      onClick={() => handleToggleComplete(task.id)}
                      className={`w-6 h-6 rounded-lg border-2 flex items-center justify-center transition-all flex-shrink-0 ${
                        isDone 
                          ? 'bg-emerald-500 border-emerald-500 text-white'
                          : 'border-slate-300 dark:border-slate-600 hover:border-indigo-500'
                      }`}
                    >
                      {isDone && <Check className="w-3.5 h-3.5" />}
                    </button>
                    <div className="min-w-0 flex-1">
                      <h4 className={`text-sm font-semibold truncate ${isDone ? 'line-through text-slate-400' : 'text-slate-900 dark:text-white'}`}>
                        {task.title}
                      </h4>
                      {task.description && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">{task.description}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center space-x-2.5">
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                      {task.project}
                    </span>
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md border ${PRIORITIES[task.priority]?.color}`}>
                      {PRIORITIES[task.priority]?.label}
                    </span>
                    <button
                      onClick={() => handleDeleteTask(task.id)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
