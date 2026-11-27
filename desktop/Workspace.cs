using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Management;
using System.Reflection;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Threading;
using System.Windows.Forms;
[assembly: AssemblyVersion("0.42.0.0")]
[assembly: AssemblyProduct("TRACE-Mem Workspace")]
class Workspace : Form {
    Process host;
    string url;
    static bool practice;
    string root = AppDomain.CurrentDomain.BaseDirectory;
    string profile;
    Label status = new Label();
    Button open = new Button();
    Button shortcuts = new Button();
    Button recovery = new Button();
    static string Hardware() {
        try {
            using(var query = new ManagementObjectSearcher("SELECT Name FROM Win32_VideoController"))
                foreach(ManagementObject gpu in query.Get())
                    return Environment.ProcessorCount+" logical CPUs · "+gpu["Name"];
        } catch (ManagementException) {} catch (UnauthorizedAccessException) {}
        return Environment.ProcessorCount+" logical CPUs";
    }
    public Workspace() {
        Text="TRACE-Mem Workspace · Beta 0.42.0";
        Font=new Font("Segoe UI",10); ClientSize=new Size(560,230);
        FormBorderStyle=FormBorderStyle.FixedDialog; MaximizeBox=false;
        StartPosition=FormStartPosition.CenterScreen;
        status.SetBounds(20,18,520,125); Controls.Add(status);
        open.Text="Open Workspace"; open.SetBounds(20,157,145,42); open.Enabled=false;
        open.Click+=(s,e)=>Process.Start(url); Controls.Add(open);
        shortcuts.Text="Create shortcuts"; shortcuts.SetBounds(180,157,150,42);
        shortcuts.Click+=(s,e)=> {
            try {
                Type t=Type.GetTypeFromProgID("WScript.Shell");
                dynamic shell=Activator.CreateInstance(t);
                foreach(var place in new[]{Environment.SpecialFolder.DesktopDirectory,Environment.SpecialFolder.Programs}) {
                    dynamic link=shell.CreateShortcut(Path.Combine(Environment.GetFolderPath(place),"TRACE-Mem Workspace Beta.lnk"));
                    link.TargetPath=Application.ExecutablePath; link.WorkingDirectory=root; link.Save();
                }
                MessageBox.Show("Desktop and Start Menu shortcuts created.");
            } catch(Exception err){ MessageBox.Show(err.Message); }
        }; Controls.Add(shortcuts);
        recovery.Text="New recovery profile"; recovery.SetBounds(345,157,190,42); recovery.Visible=false;
        recovery.Click+=(s,e)=> {
            if(MessageBox.Show("Start a separate empty profile? Your previous files will remain in place.","Recovery",MessageBoxButtons.YesNo)!=DialogResult.Yes)return;
            string child="Recovery-"+Guid.NewGuid().ToString("N");
            File.WriteAllText(Path.Combine(BaseProfile(),"active.txt"),child);
            StartBackend(Path.Combine(BaseProfile(),child));
        }; Controls.Add(recovery);
        var guide=new Button(); guide.Text="Open practice profile"; guide.SetBounds(345,157,190,42);
        guide.Visible=!practice; Controls.Add(guide);
        guide.Click+=(s,e)=>Process.Start(Application.ExecutablePath,"--practice");
        Shown+=(s,e)=> {
            try {
                string folder=BaseProfile(); Secure(folder);
                string marker=Path.Combine(folder,"active.txt");
                string child=File.Exists(marker)?File.ReadAllText(marker):"Workspace";
                if(!System.Text.RegularExpressions.Regex.IsMatch(child,@"^(Workspace|Recovery-[a-f0-9]{32})$"))
                    throw new IOException("Invalid profile selection.");
                StartBackend(Path.Combine(folder,practice?"Practice":child));
            } catch(Exception err){status.Text=err.Message;}
        };
        FormClosing+=(s,e)=>{if(host!=null && !host.HasExited){host.StandardInput.Close();}};
    }
    static string BaseProfile(){return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"TRACE-Mem Beta");}
    static void Secure(string folder){
        var acl=new DirectorySecurity();
        acl.SetAccessRuleProtection(true,false);
        var user=WindowsIdentity.GetCurrent().User;
        acl.AddAccessRule(new FileSystemAccessRule(user,FileSystemRights.FullControl,InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));
        Directory.CreateDirectory(folder,acl); Directory.SetAccessControl(folder,acl);
    }
    void StartBackend(string folder){
        try {
            Secure(folder); profile=folder;
            var psi=new ProcessStartInfo(Path.Combine(root,"runtime","python.exe"),"-B -m trace_mem.workspace_desktop \""+profile+"\"");
            psi.WorkingDirectory=root; psi.CreateNoWindow=true; psi.UseShellExecute=false;
            psi.RedirectStandardInput=true;psi.RedirectStandardOutput=true;psi.RedirectStandardError=true;
            host=Process.Start(psi);
            host.BeginErrorReadLine();
            var line=host.StandardOutput.ReadLineAsync();
            int port;
            if(!line.Wait(90000) || !Int32.TryParse(line.Result,out port) || port<1 || port>65535){
                host.StandardInput.Close();
                throw new IOException("Could not open this profile. Close other copies. If the files are damaged, choose a recovery profile.");
            }
            url="http://127.0.0.1:"+port+"/"; open.Enabled=true; recovery.Visible=false;
            status.Text="Workspace is running on this computer. Close this window to stop it.\n\n"+Hardware()+"\n\n"+url;
            Process.Start(url+(practice?"#practice":""));
        } catch(Exception err){status.Text=err.Message+"\n\nKeep the runtime folder beside the executable. See START HERE.txt.";guideRecovery();}
    }
    void guideRecovery(){recovery.BringToFront();recovery.Visible=!practice;}
    [STAThread] static void Main(string[] args){
        practice=Array.IndexOf(args,"--practice")>=0;
        bool first;
        using(var mutex=new Mutex(true,@"Local\TraceMemBeta-"+WindowsIdentity.GetCurrent().User.Value+(practice?"-practice":""),out first)){
            if(!first){MessageBox.Show("Workspace is already running. Select its launcher on the taskbar.");return;}
            Application.EnableVisualStyles();Application.Run(new Workspace());
        }
    }
}
